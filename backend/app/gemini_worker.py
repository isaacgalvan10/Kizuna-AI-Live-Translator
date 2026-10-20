import asyncio
import logging
import os
from collections import deque
from typing import TYPE_CHECKING

import httpx

from app.audio_chunking import AudioChunker, AudioSegment
from app.socket_manager import manager

from .gemini_translation import GeminiTranslator, TranslationError
from .translation_prompt import supported_languages
from .transcript_text import dedupe_overlap

if TYPE_CHECKING:
    from .church_glossary import ChurchGlossary

logger = logging.getLogger(__name__)

FLUSH_INTERVAL_SECONDS = 0.2
CONTEXT_LINES = 2


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
        chunker: AudioChunker | None = None,
        glossary: "ChurchGlossary | None" = None,
    ):
        self.room_id = room_id
        self.loop = loop
        self.chunker = chunker or AudioChunker()
        self.translator = translator or GeminiTranslator()
        self.glossary = glossary
        self.manager = socket_manager or manager
        self.debug_diagnostics = (
            _debug_diagnostics_enabled()
            if debug_diagnostics is None
            else debug_diagnostics
        )
        self._context_lines: deque[str] = deque(maxlen=CONTEXT_LINES)
        self._last_translations: dict[str, str] = {}
        self._flush_lock = asyncio.Lock()
        self.is_running = True
        self.flusher_task = (
            self.loop.create_task(self._audio_flusher_loop())
            if start_flusher
            else None
        )

    def process_audio_chunk(self, chunk: bytes):
        self.chunker.feed(chunk)

    async def _audio_flusher_loop(self):
        while self.is_running:
            try:
                await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
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
        async with self._flush_lock:
            active_langs = supported_languages(
                self.manager.get_active_languages(self.room_id)
            )
            if not active_langs:
                self.chunker.clear()
                self._last_translations.clear()
                return

            segment = self.chunker.pop_ready()
            if segment is None:
                return
            if not self.chunker.contains_new_speech(segment):
                logger.debug(
                    "gemini_skip_silence room_id=%s bytes=%d",
                    self.room_id,
                    len(segment.pcm),
                )
                return

            await self._translate_segment(segment, active_langs)

    async def _translate_segment(
        self,
        segment: AudioSegment,
        active_langs: tuple[str, ...],
    ) -> None:
        logger.debug(
            "gemini_flush room_id=%s bytes=%d overlap_bytes=%d languages=%s",
            self.room_id,
            len(segment.pcm),
            segment.overlap_bytes,
            ",".join(active_langs),
        )
        if self.debug_diagnostics:
            logger.info(
                "gemini_debug_audio room_id=%s bytes=%d non_zero=%d",
                self.room_id,
                len(segment.pcm),
                sum(1 for byte in segment.pcm if byte != 0),
            )

        context_lines = tuple(self._context_lines)
        try:
            result = await self.translator.translate(
                segment.pcm,
                active_langs,
                context_lines=context_lines,
                glossary=self.glossary,
            )
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

        previous_japanese = context_lines[-1] if context_lines else ""
        japanese = dedupe_overlap(previous_japanese, result.japanese)
        if not japanese or len(japanese) <= 1:
            return

        logger.info(
            "gemini_translated room_id=%s japanese_chars=%d languages=%s",
            self.room_id,
            len(japanese),
            ",".join(active_langs),
        )

        self.manager.record_transcript(self.room_id, japanese)

        for code in active_langs:
            translated_text = dedupe_overlap(
                self._last_translations.get(code, ""),
                result.translations.get(code, ""),
            )
            if not translated_text:
                continue
            try:
                await self.manager.broadcast_to_language(
                    japanese,
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
            else:
                self._last_translations[code] = translated_text

        self._context_lines.append(japanese)

    def start(self):
        logger.info("gemini_worker_started room_id=%s", self.room_id)

    def stop(self):
        logger.info("gemini_worker_stopping room_id=%s", self.room_id)
        self.is_running = False
        if self.flusher_task is not None:
            self.flusher_task.cancel()
        if not self.loop.is_closed():
            self.loop.create_task(self.translator.aclose())
