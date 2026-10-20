import asyncio
import logging

import httpx

from app.gemini_translation import (
    TranslationResponseError,
    TranslationResult,
)
from app.gemini_worker import MIN_BUFFER_BYTES, GeminiWorker


class FakeManager:
    def __init__(self, languages, broadcast_errors=None):
        self.languages = languages
        self.broadcast_errors = broadcast_errors or {}
        self.broadcasts = []

    def get_active_languages(self, room_id):
        return self.languages

    async def broadcast_to_language(
        self,
        japanese,
        translated,
        room_id,
        language,
    ):
        self.broadcasts.append((japanese, translated, room_id, language))
        if language in self.broadcast_errors:
            raise self.broadcast_errors[language]


class FakeTranslator:
    def __init__(self, result=None, error=None):
        self.result = result or TranslationResult(
            japanese="神は愛です。",
            translations={
                "en": "God is love.",
                "ko": "하나님은 사랑이십니다.",
            },
        )
        self.error = error
        self.calls = []
        self.closed = False

    async def translate(self, pcm_bytes, active_languages):
        self.calls.append((pcm_bytes, tuple(active_languages)))
        if self.error is not None:
            raise self.error
        return self.result

    async def aclose(self):
        self.closed = True


def make_worker(manager, translator, *, debug_diagnostics=False):
    return GeminiWorker(
        "room-1",
        asyncio.get_running_loop(),
        translator=translator,
        socket_manager=manager,
        debug_diagnostics=debug_diagnostics,
        start_flusher=False,
    )


def audio_chunk() -> bytes:
    return b"\x00\x01" * (MIN_BUFFER_BYTES // 2)


async def test_worker_flushes_once_and_broadcasts_to_each_language():
    manager = FakeManager(["en", "ko", "xx"])
    translator = FakeTranslator()
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(audio_chunk())

    await worker._flush_once()

    assert len(translator.calls) == 1
    _, languages = translator.calls[0]
    assert languages == ("en", "ko")
    assert [item[3] for item in manager.broadcasts] == ["en", "ko"]
    assert len(worker.audio_buffer) == 0


async def test_worker_does_not_requeue_after_a_broadcast_failure():
    manager = FakeManager(
        ["en", "ko"],
        broadcast_errors={"en": RuntimeError("socket down")},
    )
    translator = FakeTranslator()
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(audio_chunk())

    await worker._flush_once()

    assert len(translator.calls) == 1
    assert [item[3] for item in manager.broadcasts] == ["en", "ko"]
    assert len(worker.audio_buffer) == 0

    await worker._flush_once()

    assert len(translator.calls) == 1


async def test_worker_drops_audio_on_translation_error():
    manager = FakeManager(["en"])
    translator = FakeTranslator(
        error=TranslationResponseError("bad response"),
    )
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(audio_chunk())

    await worker._flush_once()

    assert len(translator.calls) == 1
    assert manager.broadcasts == []
    assert len(worker.audio_buffer) == 0


async def test_worker_clears_audio_when_no_supported_languages():
    manager = FakeManager(["xx"])
    translator = FakeTranslator()
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(audio_chunk())

    await worker._flush_once()

    assert translator.calls == []
    assert len(worker.audio_buffer) == 0


async def test_worker_waits_for_minimum_buffer():
    manager = FakeManager(["en"])
    translator = FakeTranslator()
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(b"\x00" * 10)

    await worker._flush_once()

    assert translator.calls == []
    assert len(worker.audio_buffer) == 10


async def test_worker_default_logs_do_not_include_transcript(caplog):
    caplog.set_level(logging.INFO, logger="app.gemini_worker")
    manager = FakeManager(["en"])
    translator = FakeTranslator()
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(audio_chunk())

    await worker._flush_once()

    assert "gemini_translated" in caplog.text
    assert "神は愛です。" not in caplog.text
    assert "God is love." not in caplog.text


async def test_worker_opt_in_diagnostics_log_audio_metadata_without_transcript(
    caplog,
):
    caplog.set_level(logging.INFO, logger="app.gemini_worker")
    manager = FakeManager(["en"])
    translator = FakeTranslator()
    worker = make_worker(
        manager,
        translator,
        debug_diagnostics=True,
    )
    worker.process_audio_chunk(audio_chunk())

    await worker._flush_once()

    assert "gemini_debug_audio" in caplog.text
    assert "non_zero=" in caplog.text
    assert "神は愛です。" not in caplog.text
    assert "God is love." not in caplog.text


async def test_worker_logs_deadline_exceeded_without_requeue(caplog):
    caplog.set_level(logging.WARNING, logger="app.gemini_worker")
    manager = FakeManager(["en"])
    translator = FakeTranslator(error=TimeoutError())
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(audio_chunk())

    await worker._flush_once()

    assert "gemini_deadline_exceeded" in caplog.text
    assert "神は愛です。" not in caplog.text
    assert len(worker.audio_buffer) == 0


async def test_worker_logs_transport_error_without_requeue(caplog):
    caplog.set_level(logging.WARNING, logger="app.gemini_worker")
    manager = FakeManager(["en"])
    translator = FakeTranslator(error=httpx.ReadTimeout("slow"))
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(audio_chunk())

    await worker._flush_once()

    assert "gemini_transport_error" in caplog.text
    assert "神は愛です。" not in caplog.text
    assert len(worker.audio_buffer) == 0
