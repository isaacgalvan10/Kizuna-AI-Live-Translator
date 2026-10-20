import asyncio
import logging
import os

import httpx

from app.socket_manager import manager

from .gemini_translation import GeminiTranslator, TranslationError
from .translation_prompt import supported_languages

logger = logging.getLogger(__name__)

MIN_BUFFER_BYTES = int(32000 * 1.5)
MAX_BUFFER_BYTES = int(32000 * 5.0)


def _debug_diagnostics_enabled() -> bool:
    return os.getenv("KIZUNA_DEBUG_DIAGNOSTICS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class GeminiWorker:
    def __init__(
        self,
        room_id: str,
        loop: asyncio.AbstractEventLoop,
        *,
        translator: GeminiTranslator | None = None,
        socket_manager=None,
        debug_diagnostics: bool | None = None,
        start_flusher: bool = True,
    ):
        self.room_id = room_id
        self.loop = loop
        self.audio_buffer = bytearray()
        self.buffer_lock = asyncio.Lock()
        self.translator = translator or GeminiTranslator()
        self.manager = socket_manager or manager
        self.debug_diagnostics = (
            _debug_diagnostics_enabled()
            if debug_diagnostics is None
            else debug_diagnostics
        )
        self.is_running = True
        self.flusher_task = (
            self.loop.create_task(self._audio_flusher_loop())
            if start_flusher
            else None
        )

    def process_audio_chunk(self, chunk: bytes):
        self.audio_buffer.extend(chunk)

    async def _audio_flusher_loop(self):
        while self.is_running:
            try:
                await asyncio.sleep(3.0)
                await self._flush_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "gemini_worker_loop_error room_id=%s",
                    self.room_id,
                )
                await asyncio.sleep(1.0)

    async def _flush_once(self) -> None:
        active_langs = supported_languages(
            self.manager.get_active_languages(self.room_id)
        )
        async with self.buffer_lock:
            if not active_langs:
                self.audio_buffer.clear()
                return
            if len(self.audio_buffer) < MIN_BUFFER_BYTES:
                return
            chunk_size = min(len(self.audio_buffer), MAX_BUFFER_BYTES)
            raw_pcm = bytes(self.audio_buffer[:chunk_size])
            del self.audio_buffer[:chunk_size]

        logger.debug(
            "gemini_flush room_id=%s bytes=%d languages=%s",
            self.room_id,
            chunk_size,
            ",".join(active_langs),
        )
        if self.debug_diagnostics:
            logger.info(
                "gemini_debug_audio room_id=%s bytes=%d non_zero=%d",
                self.room_id,
                len(raw_pcm),
                sum(1 for byte in raw_pcm if byte != 0),
            )

        try:
            result = await self.translator.translate(raw_pcm, active_langs)
        except TranslationError as exc:
            logger.warning(
                "gemini_translation_failed room_id=%s error=%s",
                self.room_id,
                type(exc).__name__,
            )
            return
        except TimeoutError:
            logger.warning(
                "gemini_deadline_exceeded room_id=%s",
                self.room_id,
            )
            return
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "gemini_http_error room_id=%s status=%d",
                self.room_id,
                exc.response.status_code,
            )
            return
        except httpx.TransportError as exc:
            logger.warning(
                "gemini_transport_error room_id=%s error=%s",
                self.room_id,
                type(exc).__name__,
            )
            return

        if not result.japanese or len(result.japanese) <= 1:
            return

        logger.info(
            "gemini_translated room_id=%s japanese_chars=%d languages=%s",
            self.room_id,
            len(result.japanese),
            ",".join(active_langs),
        )

        for code in active_langs:
            translated_text = result.translations.get(code, "")
            if not translated_text:
                continue
            try:
                await self.manager.broadcast_to_language(
                    result.japanese,
                    translated_text,
                    self.room_id,
                    code,
                )
            except Exception:
                logger.exception(
                    "gemini_broadcast_failed room_id=%s language=%s",
                    self.room_id,
                    code,
                )

    def start(self):
        logger.info("gemini_worker_started room_id=%s", self.room_id)

    def stop(self):
        logger.info("gemini_worker_stopping room_id=%s", self.room_id)
        self.is_running = False
        if self.flusher_task is not None:
            self.flusher_task.cancel()
        if not self.loop.is_closed():
            self.loop.create_task(self.translator.aclose())
