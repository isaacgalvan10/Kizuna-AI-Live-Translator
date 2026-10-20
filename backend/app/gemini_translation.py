import asyncio
import base64
import io
import json
import logging
import os
import random
import wave
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

import httpx

from .translation_prompt import (
    build_prompt,
    build_response_schema,
    supported_languages,
)

DEFAULT_MODEL = "gemini-3.8-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MAX_OUTPUT_TOKENS = 2048
MAX_ATTEMPTS = 3
BASE_RETRY_DELAY = 0.5
MAX_RETRY_DELAY = 4.0
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
BLOCKED_FINISH_REASONS = frozenset(
    {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}
)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-2.5-flash": (1.00, 2.50),
}

logger = logging.getLogger(__name__)


class TranslationError(Exception):
    pass


class NoActiveLanguagesError(TranslationError):
    pass


class GeminiConfigurationError(TranslationError):
    pass


class TranslationResponseError(TranslationError):
    pass


@dataclass(frozen=True)
class GeminiUsage:
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    total_tokens: int
    estimated_cost_usd: float


@dataclass(frozen=True)
class TranslationResult:
    japanese: str
    translations: dict[str, str]
    usage: GeminiUsage | None = None


def normalize_model(model: str | None) -> str:
    value = (model or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL).strip()
    if value.startswith("models/"):
        value = value.removeprefix("models/")
    return value or DEFAULT_MODEL


def pcm_to_wav(
    pcm_bytes: bytes,
    sample_rate: int = 16000,
    sample_width: int = 2,
    channels: int = 1,
) -> bytes:
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return wav_io.getvalue()


def build_generation_config(
    active_languages: Sequence[str],
    model: str,
) -> dict:
    config = {
        "temperature": 0.1,
        "maxOutputTokens": MAX_OUTPUT_TOKENS,
        "responseMimeType": "application/json",
        "responseSchema": build_response_schema(active_languages),
    }
    if normalize_model(model).startswith("gemini-3"):
        config["thinkingConfig"] = {"thinkingLevel": "LOW"}
    return config


def build_request_payload(
    pcm_bytes: bytes,
    active_languages: Sequence[str],
    *,
    context_lines: Sequence[str] = (),
    model: str = DEFAULT_MODEL,
) -> dict:
    languages = supported_languages(active_languages)
    if not languages:
        raise NoActiveLanguagesError("At least one supported language is required.")

    encoded_audio = base64.b64encode(pcm_to_wav(pcm_bytes)).decode("ascii")
    return {
        "systemInstruction": {
            "parts": [
                {
                    "text": build_prompt(
                        languages,
                        context_lines=context_lines,
                    )
                }
            ]
        },
        "contents": [
            {
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": "audio/wav",
                            "data": encoded_audio,
                        }
                    },
                    {
                        "text": (
                            "Transcribe and translate this Japanese sermon "
                            "audio chunk."
                        )
                    },
                ]
            }
        ],
        "generationConfig": build_generation_config(languages, model),
    }


def extract_response_text(response_json: dict) -> str:
    if not isinstance(response_json, dict):
        raise TranslationResponseError("Gemini returned an unexpected response body.")

    prompt_feedback = response_json.get("promptFeedback") or {}
    block_reason = prompt_feedback.get("blockReason")
    if block_reason:
        raise TranslationResponseError(
            f"Gemini blocked the prompt: {block_reason}."
        )

    candidates = response_json.get("candidates") or []
    if not candidates:
        raise TranslationResponseError("Gemini returned no candidates.")

    candidate = candidates[0] or {}
    finish_reason = str(candidate.get("finishReason") or "").upper()
    if finish_reason in BLOCKED_FINISH_REASONS:
        raise TranslationResponseError(
            f"Gemini stopped with finish reason {finish_reason}."
        )
    if finish_reason not in ("", "STOP"):
        raise TranslationResponseError(
            f"Gemini stopped with finish reason {finish_reason}."
        )

    content = candidate.get("content") or {}
    parts = content.get("parts") or []
    raw_text = "".join(
        part.get("text", "") for part in parts if isinstance(part, dict)
    ).strip()
    if not raw_text:
        raise TranslationResponseError("Gemini returned an empty response.")
    return raw_text


def parse_translation_response(
    raw_text: str,
    active_languages: Sequence[str],
) -> TranslationResult:
    languages = supported_languages(active_languages)
    if not languages:
        raise NoActiveLanguagesError("At least one supported language is required.")

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise TranslationResponseError("Gemini returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise TranslationResponseError(
            "Gemini returned JSON that is not an object."
        )

    japanese = data.get("japanese")
    translations = data.get("translations")
    if not isinstance(japanese, str) or not isinstance(translations, dict):
        raise TranslationResponseError(
            "Gemini response is missing the required JSON fields."
        )

    parsed_translations: dict[str, str] = {}
    for code in languages:
        value = translations.get(code)
        if not isinstance(value, str):
            raise TranslationResponseError(
                f"Gemini response is missing translation {code!r}."
            )
        parsed_translations[code] = value.strip()

    return TranslationResult(
        japanese=japanese.strip(),
        translations=parsed_translations,
    )


def _token_count(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def price_for_model(model: str) -> tuple[float, float] | None:
    normalized = normalize_model(model)
    for prefix, pricing in MODEL_PRICING.items():
        if normalized.startswith(prefix):
            return pricing
    return None


def estimate_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int,
) -> float:
    pricing = price_for_model(model)
    if pricing is None:
        return 0.0
    input_price, output_price = pricing
    return (
        input_tokens * input_price
        + (output_tokens + thinking_tokens) * output_price
    ) / 1_000_000


def parse_usage(response_json: dict, model: str) -> GeminiUsage | None:
    metadata = response_json.get("usageMetadata")
    if not isinstance(metadata, dict) or not metadata:
        return None
    input_tokens = _token_count(metadata.get("promptTokenCount"))
    output_tokens = _token_count(metadata.get("candidatesTokenCount"))
    thinking_tokens = _token_count(metadata.get("thoughtsTokenCount"))
    total_tokens = _token_count(metadata.get("totalTokenCount"))
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens + thinking_tokens
    return GeminiUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_tokens=thinking_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimate_cost_usd(
            model,
            input_tokens,
            output_tokens,
            thinking_tokens,
        ),
    )


class GeminiTranslator:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ):
        key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY")
        self.api_key = key.strip() if key else None
        self.model = normalize_model(model)
        self.url = f"{GEMINI_BASE_URL}/models/{self.model}:generateContent"
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=50,
                max_keepalive_connections=20,
            )
        )
        self._sleep = sleep or asyncio.sleep

    async def translate(
        self,
        pcm_bytes: bytes,
        active_languages: Sequence[str],
        *,
        context_lines: Sequence[str] = (),
    ) -> TranslationResult:
        languages = supported_languages(active_languages)
        if not languages:
            raise NoActiveLanguagesError(
                "At least one supported language is required."
            )
        if not self.api_key:
            raise GeminiConfigurationError("GEMINI_API_KEY is not set.")

        payload = build_request_payload(
            pcm_bytes,
            languages,
            context_lines=context_lines,
            model=self.model,
        )
        response = await self._post_with_retries(payload)
        try:
            response_json = response.json()
        except ValueError as exc:
            raise TranslationResponseError(
                "Gemini returned a non-JSON HTTP response."
            ) from exc
        parsed = parse_translation_response(
            extract_response_text(response_json),
            languages,
        )
        usage = parse_usage(response_json, self.model)
        self._log_usage(usage)
        return TranslationResult(
            japanese=parsed.japanese,
            translations=parsed.translations,
            usage=usage,
        )

    async def _post_with_retries(self, payload: dict) -> httpx.Response:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = await self.http_client.post(
                    self.url,
                    headers={"x-goog-api-key": self.api_key},
                    json=payload,
                    timeout=20.0,
                )
            except httpx.TransportError:
                if attempt >= MAX_ATTEMPTS:
                    raise
                delay = self._retry_delay(attempt)
                logger.warning(
                    "gemini_retry attempt=%d reason=transport_error delay=%.2fs",
                    attempt,
                    delay,
                )
                await self._sleep(delay)
                continue
            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt >= MAX_ATTEMPTS:
                    response.raise_for_status()
                delay = self._retry_delay(attempt)
                logger.warning(
                    "gemini_retry attempt=%d status=%d delay=%.2fs",
                    attempt,
                    response.status_code,
                    delay,
                )
                await self._sleep(delay)
                continue
            response.raise_for_status()
            return response
        raise RuntimeError("Gemini retry loop exhausted without a response.")

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        base = min(MAX_RETRY_DELAY, BASE_RETRY_DELAY * (2 ** (attempt - 1)))
        return base + random.uniform(0, base * 0.25)

    def _log_usage(self, usage: GeminiUsage | None) -> None:
        if usage is None:
            logger.info("gemini_usage model=%s usage=unavailable", self.model)
            return
        logger.info(
            "gemini_usage model=%s input_tokens=%d output_tokens=%d "
            "thinking_tokens=%d estimated_cost_usd=%.6f",
            self.model,
            usage.input_tokens,
            usage.output_tokens,
            usage.thinking_tokens,
            usage.estimated_cost_usd,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self.http_client.aclose()
