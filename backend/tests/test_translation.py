import asyncio
import json
import logging

import httpx
import pytest

from app.church_glossary import parse_church_glossary
from app.gemini_translation import (
    GeminiConfigurationError,
    GeminiTranslator,
    NoActiveLanguagesError,
    REQUEST_TIMEOUT_SECONDS,
    TranslationResponseError,
    build_request_payload,
    build_response_schema,
    normalize_model,
    parse_translation_response,
)
from app.translation_prompt import build_prompt, supported_languages


def gemini_response(
    data: dict,
    finish_reason: str = "STOP",
    usage: dict | None = None,
) -> dict:
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": json.dumps(data, ensure_ascii=False)},
                    ]
                },
                "finishReason": finish_reason,
            }
        ]
    }
    if usage is not None:
        response["usageMetadata"] = usage
    return response


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload, ensure_ascii=False)

    def raise_for_status(self):
        if self.status_code < 400:
            return
        request = httpx.Request("POST", "https://example.test")
        response = httpx.Response(
            self.status_code,
            request=request,
            text=self.text,
        )
        raise httpx.HTTPStatusError(
            "request failed",
            request=request,
            response=response,
        )

    def json(self):
        return self._payload


class FakeHttpClient:
    def __init__(self, *responses: FakeResponse | Exception):
        self.responses = list(responses)
        self.calls: list[dict] = []
        self.closed = False

    async def post(self, url, *, headers=None, json=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def aclose(self):
        self.closed = True


class HangingHttpClient:
    async def post(self, url, *, headers=None, json=None, timeout=None):
        await asyncio.sleep(1)


def make_translator(
    response: FakeResponse,
    *,
    model: str | None = "gemini-3.8-flash",
    api_key: str | None = "test-key",
    sleep=None,
) -> tuple[GeminiTranslator, FakeHttpClient]:
    client = FakeHttpClient(response)
    translator = GeminiTranslator(
        api_key=api_key,
        model=model,
        http_client=client,
        sleep=sleep,
    )
    return translator, client


def test_supported_languages_filters_and_deduplicates():
    assert supported_languages(["en", "xx", "ko", "en"]) == ("en", "ko")


def test_prompt_lists_only_requested_languages_and_json_contract():
    prompt = build_prompt(["en", "ko"])

    assert '- "en": English' in prompt
    assert '- "ko": Korean' in prompt
    assert "zh-hans" not in prompt
    assert '"japanese"' in prompt
    assert '"translations"' in prompt
    assert "ESV" in prompt
    assert "개역개정" in prompt
    assert "新共同訳" in prompt


def test_prompt_includes_recent_context():
    prompt = build_prompt(
        ["en"],
        context_lines=["前の文。", "もう一つの文。"],
    )

    assert "前の文。" in prompt
    assert "もう一つの文。" in prompt


def test_prompt_warns_that_the_audio_overlap_must_not_be_repeated():
    prompt = build_prompt(["en"], context_lines=["前の文。"])

    assert "overlap" in prompt.lower()
    assert "do not repeat" in prompt.lower()


def test_prompt_keeps_terminology_consistent_with_recent_context():
    prompt = build_prompt(["en"], context_lines=["前の文。"])

    assert "RECENT CONTEXT" in prompt
    assert "consistent" in prompt.lower()


def sample_glossary():
    return parse_church_glossary(
        {
            "names": [
                {
                    "japanese": "山田牧師",
                    "en": "Pastor Yamada",
                    "ko": "야마다 목사",
                    "zh-hans": "山田牧师",
                }
            ],
            "terms": [
                {
                    "japanese": "聖餐",
                    "en": "Holy Communion",
                    "ko": "성찬",
                    "zh-hans": "圣餐",
                }
            ],
            "style": {
                "en": "Use short, warm sentences.",
                "ko": "Use short sentences in formal polite style.",
            },
            "scripture": {
                "source": "新改訳2017",
                "en": "NIV",
                "ko": "새번역",
            },
        }
    )


def test_prompt_injects_glossary_names_and_terms_for_active_languages():
    prompt = build_prompt(["en", "ko"], glossary=sample_glossary())

    assert "CHURCH GLOSSARY" in prompt
    assert "山田牧師" in prompt
    assert "Pastor Yamada" in prompt
    assert "야마다 목사" in prompt
    assert "聖餐" in prompt
    assert "Holy Communion" in prompt
    assert "성찬" in prompt
    assert "山田牧师" not in prompt
    assert "圣餐" not in prompt


def test_prompt_injects_chinese_glossary_entries_when_chinese_is_active():
    prompt = build_prompt(["zh-hans"], glossary=sample_glossary())

    assert "山田牧師" in prompt
    assert "山田牧师" in prompt
    assert "圣餐" in prompt
    assert "Pastor Yamada" not in prompt
    assert "야마다 목사" not in prompt


def test_prompt_injects_traditional_chinese_glossary_entries():
    glossary = parse_church_glossary(
        {"terms": [{"japanese": "教会", "zh-hant": "教會"}]}
    )

    prompt = build_prompt(["zh-hant"], glossary=glossary)

    assert "zh-hant: 教會" in prompt


def test_prompt_omits_glossary_entries_without_an_active_translation():
    glossary = parse_church_glossary(
        {
            "names": [
                {"japanese": "山田牧師", "en": "Pastor Yamada"},
                {"japanese": "田中牧師", "ko": "다나카 목사"},
            ]
        }
    )

    prompt = build_prompt(["en"], glossary=glossary)

    assert "山田牧師" in prompt
    assert "田中牧師" not in prompt


def test_prompt_applies_glossary_style_and_scripture_overrides():
    prompt = build_prompt(["en", "ko"], glossary=sample_glossary())

    assert "Use short, warm sentences." in prompt
    assert "Use short sentences in formal polite style." in prompt
    assert "新改訳2017" in prompt
    assert "NIV" in prompt
    assert "새번역" in prompt
    assert "overrid" in prompt.lower()


def test_prompt_without_a_glossary_keeps_defaults_and_has_no_section():
    prompt = build_prompt(["en", "ko"])

    assert "CHURCH GLOSSARY" not in prompt
    assert "ESV" in prompt
    assert "개역개정" in prompt
    assert "新共同訳" in prompt


def test_prompt_ignores_an_empty_glossary():
    prompt = build_prompt(["en"], glossary=parse_church_glossary({}))

    assert "CHURCH GLOSSARY" not in prompt


def test_prompt_keeps_both_recent_context_and_glossary():
    prompt = build_prompt(
        ["en"],
        context_lines=["前の文。"],
        glossary=sample_glossary(),
    )

    assert "前の文。" in prompt
    assert "山田牧師" in prompt


def test_response_schema_has_only_requested_translations():
    schema = build_response_schema(["en", "zh-hans"])
    translations = schema["properties"]["translations"]

    assert set(translations["properties"]) == {"en", "zh-hans"}
    assert translations["required"] == ["en", "zh-hans"]


def test_parse_structured_response():
    result = parse_translation_response(
        json.dumps(
            {
                "japanese": " 神は愛です。 ",
                "translations": {
                    "en": " God is love. ",
                    "ko": " 하나님은 사랑이십니다. ",
                },
            },
            ensure_ascii=False,
        ),
        ["en", "ko"],
    )

    assert result.japanese == "神は愛です。"
    assert result.translations == {
        "en": "God is love.",
        "ko": "하나님은 사랑이십니다.",
    }


def test_parse_rejects_invalid_json():
    with pytest.raises(TranslationResponseError, match="invalid JSON"):
        parse_translation_response("not json", ["en"])


def test_parse_rejects_a_missing_translation():
    with pytest.raises(TranslationResponseError, match="missing translation"):
        parse_translation_response(
            json.dumps(
                {
                    "japanese": "神は愛です。",
                    "translations": {"en": "God is love."},
                },
                ensure_ascii=False,
            ),
            ["en", "ko"],
        )


async def test_translator_batch_translates_history_lines_in_one_request():
    data = {
        "translations": {
            "en": ["God is love.", "God is light."],
        }
    }
    translator, client = make_translator(FakeResponse(gemini_response(data)))

    result = await translator.translate_lines(
        ["神は愛です。", "神は光です。"],
        ["en"],
    )

    assert len(client.calls) == 1
    call = client.calls[0]
    assert "test-key" not in call["url"]
    assert call["headers"] == {"x-goog-api-key": "test-key"}
    assert call["timeout"] == REQUEST_TIMEOUT_SECONDS

    payload = call["json"]
    system_prompt = payload["systemInstruction"]["parts"][0]["text"]
    assert "2 Japanese transcript lines" in system_prompt
    assert '- "en": English' in system_prompt
    assert json.loads(payload["contents"][0]["parts"][0]["text"]) == {
        "lines": ["神は愛です。", "神は光です。"]
    }
    schema = payload["generationConfig"]["responseSchema"]
    assert schema["properties"]["translations"]["properties"]["en"]["type"] == (
        "ARRAY"
    )

    assert result.translations == {
        "en": ["God is love.", "God is light."],
    }


async def test_translator_rejects_the_wrong_number_of_backfill_lines():
    translator, _ = make_translator(
        FakeResponse(
            gemini_response(
                {"translations": {"en": ["Only one line."]}}
            )
        )
    )

    with pytest.raises(TranslationResponseError, match="wrong number"):
        await translator.translate_lines(
            ["神は愛です。", "神は光です。"],
            ["en"],
        )


async def test_translator_injects_the_glossary_into_a_backfill_request():
    translator, client = make_translator(
        FakeResponse(
            gemini_response(
                {"translations": {"en": ["Pastor Yamada spoke."]}}
            )
        )
    )
    glossary = sample_glossary()

    await translator.translate_lines(
        ["山田牧師が話しました。"],
        ["en"],
        glossary=glossary,
    )

    prompt = client.calls[0]["json"]["systemInstruction"]["parts"][0]["text"]
    assert "CHURCH GLOSSARY" in prompt
    assert "山田牧師" in prompt
    assert "Pastor Yamada" in prompt


async def test_translator_skips_http_when_there_are_no_backfill_lines():
    translator, client = make_translator(
        FakeResponse(gemini_response({"translations": {"en": []}}))
    )

    result = await translator.translate_lines([], ["en"])

    assert client.calls == []
    assert result.translations == {"en": []}


async def test_translator_makes_one_request_for_all_active_languages():
    data = {
        "japanese": "神は愛です。",
        "translations": {
            "en": "God is love.",
            "ko": "하나님은 사랑이십니다.",
        },
    }
    translator, client = make_translator(FakeResponse(gemini_response(data)))

    result = await translator.translate(b"\x00\x01" * 480, ["en", "ko"])

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.8-flash:generateContent"
    )
    assert call["headers"] == {"x-goog-api-key": "test-key"}
    assert "test-key" not in call["url"]
    assert call["timeout"] == REQUEST_TIMEOUT_SECONDS

    payload = call["json"]
    assert payload["systemInstruction"]["parts"][0]["text"] == build_prompt(
        ["en", "ko"]
    )
    config = payload["generationConfig"]
    assert config["maxOutputTokens"] == 2048
    assert config["responseMimeType"] == "application/json"
    assert config["thinkingConfig"] == {"thinkingLevel": "LOW"}
    assert set(
        config["responseSchema"]["properties"]["translations"]["properties"]
    ) == {"en", "ko"}

    assert result.japanese == "神は愛です。"
    assert result.translations == {
        "en": "God is love.",
        "ko": "하나님은 사랑이십니다.",
    }


async def test_translator_injects_the_church_glossary_into_the_request():
    translator, client = make_translator(
        FakeResponse(
            gemini_response(
                {
                    "japanese": "神は愛です。",
                    "translations": {
                        "en": "God is love.",
                        "ko": "하나님은 사랑이십니다.",
                    },
                }
            )
        )
    )
    glossary = sample_glossary()

    await translator.translate(
        b"\x00\x01" * 480,
        ["en", "ko"],
        glossary=glossary,
    )

    prompt = client.calls[0]["json"]["systemInstruction"]["parts"][0]["text"]
    assert prompt == build_prompt(["en", "ko"], glossary=glossary)
    assert "CHURCH GLOSSARY" in prompt
    assert "山田牧師" in prompt


async def test_translator_uses_configured_model():
    translator, client = make_translator(
        FakeResponse(
            gemini_response(
                {
                    "japanese": "神は愛です。",
                    "translations": {"en": "God is love."},
                }
            )
        ),
        model="gemini-3.5-flash-lite",
    )

    await translator.translate(b"\x00\x01" * 480, ["en"])

    assert client.calls[0]["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.5-flash-lite:generateContent"
    )


async def test_translator_reads_model_from_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    translator, _ = make_translator(
        FakeResponse(
            gemini_response(
                {
                    "japanese": "神は愛です。",
                    "translations": {"en": "God is love."},
                }
            )
        ),
        model=None,
    )

    assert translator.model == "gemini-3.5-flash-lite"


async def test_translator_omits_thinking_config_for_older_models():
    translator, client = make_translator(
        FakeResponse(
            gemini_response(
                {
                    "japanese": "神は愛です。",
                    "translations": {"en": "God is love."},
                }
            )
        ),
        model="gemini-2.5-flash",
    )

    await translator.translate(b"\x00\x01" * 480, ["en"])

    assert "thinkingConfig" not in client.calls[0]["json"]["generationConfig"]


async def test_translator_skips_http_for_empty_or_unknown_languages():
    translator, client = make_translator(
        FakeResponse(
            gemini_response(
                {
                    "japanese": "神は愛です。",
                    "translations": {"en": "God is love."},
                }
            )
        )
    )

    with pytest.raises(NoActiveLanguagesError):
        await translator.translate(b"\x00\x01" * 480, [])
    with pytest.raises(NoActiveLanguagesError):
        await translator.translate(b"\x00\x01" * 480, ["xx"])

    assert client.calls == []


async def test_translator_rejects_a_blocked_prompt():
    translator, _ = make_translator(
        FakeResponse({"promptFeedback": {"blockReason": "SAFETY"}})
    )

    with pytest.raises(TranslationResponseError, match="blocked"):
        await translator.translate(b"\x00\x01" * 480, ["en"])


async def test_translator_rejects_malformed_json():
    translator, _ = make_translator(
        FakeResponse(
            {
                "candidates": [
                    {
                        "content": {"parts": [{"text": "not json"}]},
                        "finishReason": "STOP",
                    }
                ]
            }
        )
    )

    with pytest.raises(TranslationResponseError, match="invalid JSON"):
        await translator.translate(b"\x00\x01" * 480, ["en"])


async def test_translator_rejects_a_non_stop_finish_reason():
    translator, _ = make_translator(
        FakeResponse(
            {
                "candidates": [
                    {
                        "content": {"parts": [{"text": "{}"}]},
                        "finishReason": "MAX_TOKENS",
                    }
                ]
            }
        )
    )

    with pytest.raises(TranslationResponseError, match="MAX_TOKENS"):
        await translator.translate(b"\x00\x01" * 480, ["en"])


async def test_translator_requires_an_api_key():
    translator, client = make_translator(
        FakeResponse(
            gemini_response(
                {
                    "japanese": "神は愛です。",
                    "translations": {"en": "God is love."},
                }
            )
        ),
        api_key="",
    )

    with pytest.raises(GeminiConfigurationError):
        await translator.translate(b"\x00\x01" * 480, ["en"])

    assert client.calls == []


async def test_translator_retries_a_retryable_status():
    data = {
        "japanese": "神は愛です。",
        "translations": {"en": "God is love."},
    }
    sleeps: list[float] = []

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    client = FakeHttpClient(
        FakeResponse({"error": "busy"}, status_code=429),
        FakeResponse(gemini_response(data)),
    )
    translator = GeminiTranslator(
        api_key="test-key",
        model="gemini-3.8-flash",
        http_client=client,
        sleep=fake_sleep,
    )

    result = await translator.translate(b"\x00\x01" * 480, ["en"])

    assert result.translations == {"en": "God is love."}
    assert len(client.calls) == 2
    assert len(sleeps) == 1
    assert 0.5 <= sleeps[0] <= 0.625


async def test_translator_retries_a_timeout():
    data = {
        "japanese": "神は愛です。",
        "translations": {"en": "God is love."},
    }
    sleeps: list[float] = []

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    client = FakeHttpClient(
        httpx.ReadTimeout("slow"),
        FakeResponse(gemini_response(data)),
    )
    translator = GeminiTranslator(
        api_key="test-key",
        model="gemini-3.8-flash",
        http_client=client,
        sleep=fake_sleep,
    )

    result = await translator.translate(b"\x00\x01" * 480, ["en"])

    assert result.translations == {"en": "God is love."}
    assert len(client.calls) == 2
    assert len(sleeps) == 1


async def test_translator_stops_after_max_attempts():
    sleeps: list[float] = []

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    client = FakeHttpClient(
        FakeResponse({"error": "busy"}, status_code=503),
        FakeResponse({"error": "busy"}, status_code=503),
        FakeResponse({"error": "busy"}, status_code=503),
    )
    translator = GeminiTranslator(
        api_key="test-key",
        model="gemini-3.8-flash",
        http_client=client,
        sleep=fake_sleep,
    )

    with pytest.raises(httpx.HTTPStatusError):
        await translator.translate(b"\x00\x01" * 480, ["en"])

    assert len(client.calls) == 3
    assert len(sleeps) == 2


async def test_translator_does_not_retry_a_non_retryable_status():
    sleeps: list[float] = []

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    client = FakeHttpClient(FakeResponse({"error": "bad"}, status_code=400))
    translator = GeminiTranslator(
        api_key="test-key",
        model="gemini-3.8-flash",
        http_client=client,
        sleep=fake_sleep,
    )

    with pytest.raises(httpx.HTTPStatusError):
        await translator.translate(b"\x00\x01" * 480, ["en"])

    assert len(client.calls) == 1
    assert sleeps == []


async def test_translator_records_usage_and_cost():
    data = {
        "japanese": "神は愛です。",
        "translations": {"en": "God is love."},
    }
    translator, _ = make_translator(
        FakeResponse(
            gemini_response(
                data,
                usage={
                    "promptTokenCount": 1000,
                    "candidatesTokenCount": 100,
                    "thoughtsTokenCount": 50,
                    "totalTokenCount": 1150,
                },
            )
        )
    )

    result = await translator.translate(b"\x00\x01" * 480, ["en"])

    assert result.usage is not None
    assert result.usage.input_tokens == 1000
    assert result.usage.output_tokens == 100
    assert result.usage.thinking_tokens == 50
    assert result.usage.total_tokens == 1150
    assert result.usage.estimated_cost_usd == pytest.approx(
        (1000 * 0.75 + 150 * 3.75) / 1_000_000
    )


async def test_translator_leaves_usage_empty_when_metadata_is_missing():
    translator, _ = make_translator(
        FakeResponse(
            gemini_response(
                {
                    "japanese": "神は愛です。",
                    "translations": {"en": "God is love."},
                }
            )
        )
    )

    result = await translator.translate(b"\x00\x01" * 480, ["en"])

    assert result.usage is None


async def test_translator_logs_usage_before_rejecting_a_blocked_response(caplog):
    caplog.set_level(logging.INFO, logger="app.gemini_translation")
    translator, _ = make_translator(
        FakeResponse(
            {
                "promptFeedback": {"blockReason": "SAFETY"},
                "usageMetadata": {
                    "promptTokenCount": 100,
                    "candidatesTokenCount": 0,
                    "thoughtsTokenCount": 0,
                    "totalTokenCount": 100,
                },
            }
        )
    )

    with pytest.raises(TranslationResponseError, match="blocked"):
        await translator.translate(b"\x00\x01" * 480, ["en"])

    assert "gemini_usage" in caplog.text
    assert "input_tokens=100" in caplog.text


async def test_translator_rejects_an_empty_response():
    translator, _ = make_translator(
        FakeResponse(
            {
                "candidates": [
                    {
                        "content": {"parts": []},
                        "finishReason": "STOP",
                    }
                ]
            }
        )
    )

    with pytest.raises(TranslationResponseError, match="empty response"):
        await translator.translate(b"\x00\x01" * 480, ["en"])


async def test_translator_enforces_an_overall_retry_budget(monkeypatch):
    monkeypatch.setattr(
        "app.gemini_translation.TOTAL_RETRY_BUDGET_SECONDS",
        0.05,
    )
    translator = GeminiTranslator(
        api_key="test-key",
        http_client=HangingHttpClient(),
    )

    with pytest.raises(TimeoutError):
        await translator.translate(b"\x00\x01" * 480, ["en"])


async def test_translator_does_not_close_an_injected_client():
    translator, client = make_translator(
        FakeResponse(
            gemini_response(
                {
                    "japanese": "神は愛です。",
                    "translations": {"en": "God is love."},
                }
            )
        )
    )

    await translator.aclose()

    assert client.closed is False


def test_build_request_payload_requires_a_supported_language():
    with pytest.raises(NoActiveLanguagesError):
        build_request_payload(b"\x00\x01", [])


def test_normalize_model_removes_the_models_prefix():
    assert normalize_model("models/gemini-3.8-flash") == "gemini-3.8-flash"
