import asyncio
import logging

import httpx

from app.church_glossary import parse_church_glossary
from app.gemini_translation import (
    TranslationResponseError,
    TranslationResult,
)
from app.gemini_worker import GeminiWorker

SPEECH_SAMPLE = b"\xd0\x07"


class FakeManager:
    def __init__(self, languages, broadcast_errors=None):
        self.languages = languages
        self.broadcast_errors = broadcast_errors or {}
        self.broadcasts = []
        self.transcripts = []

    def get_active_languages(self, room_id):
        return self.languages

    def record_transcript(self, room_id, japanese):
        self.transcripts.append((room_id, japanese))

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
    def __init__(self, results=None, error=None):
        self.results = list(results) if results is not None else [
            TranslationResult(
                japanese="神は愛です。",
                translations={
                    "en": "God is love.",
                    "ko": "하나님은 사랑이십니다.",
                },
            )
        ]
        self.error = error
        self.calls = []
        self.closed = False

    async def translate(
        self,
        pcm_bytes,
        active_languages,
        *,
        context_lines=(),
        glossary=None,
    ):
        self.calls.append(
            (
                pcm_bytes,
                tuple(active_languages),
                tuple(context_lines),
                glossary,
            )
        )
        if self.error is not None:
            raise self.error
        if len(self.results) > 1:
            return self.results.pop(0)
        return self.results[0]

    async def aclose(self):
        self.closed = True


def speech(seconds: float) -> bytes:
    return SPEECH_SAMPLE * int(16000 * seconds)


def silence(seconds: float) -> bytes:
    return b"\x00\x00" * int(16000 * seconds)


def audio_chunk() -> bytes:
    return speech(1.5) + silence(0.35)


def make_worker(manager, translator, *, debug_diagnostics=False, glossary=None):
    return GeminiWorker(
        "room-1",
        asyncio.get_running_loop(),
        translator=translator,
        socket_manager=manager,
        debug_diagnostics=debug_diagnostics,
        start_flusher=False,
        glossary=glossary,
    )


async def test_worker_flushes_once_and_broadcasts_to_each_language():
    manager = FakeManager(["en", "ko", "xx"])
    translator = FakeTranslator()
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(audio_chunk())

    await worker._flush_once()

    assert len(translator.calls) == 1
    pcm, languages, context, _ = translator.calls[0]
    assert pcm == speech(1.5)
    assert languages == ("en", "ko")
    assert context == ()
    assert [item[3] for item in manager.broadcasts] == ["en", "ko"]
    assert worker.chunker.pending_new_bytes == int(32000 * 0.35)


async def test_worker_records_one_shared_transcript_line_per_chunk():
    manager = FakeManager(["en", "ko"])
    translator = FakeTranslator()
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(audio_chunk())

    await worker._flush_once()

    assert manager.transcripts == [("room-1", "神は愛です。")]


async def test_worker_records_no_transcript_without_listeners():
    manager = FakeManager([])
    translator = FakeTranslator()
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(audio_chunk())

    await worker._flush_once()

    assert translator.calls == []
    assert manager.transcripts == []


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
    assert worker.chunker.pending_new_bytes == int(32000 * 0.35)


async def test_worker_clears_audio_when_no_supported_languages():
    manager = FakeManager(["xx"])
    translator = FakeTranslator()
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(audio_chunk())

    await worker._flush_once()

    assert translator.calls == []
    assert len(worker.chunker.buffer) == 0


async def test_worker_waits_for_minimum_buffer():
    manager = FakeManager(["en"])
    translator = FakeTranslator()
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(b"\x00" * 10)

    await worker._flush_once()

    assert translator.calls == []
    assert len(worker.chunker.buffer) == 10


async def test_worker_skips_silence_without_calling_the_model():
    manager = FakeManager(["en"])
    translator = FakeTranslator()
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(silence(2.0))

    await worker._flush_once()

    assert translator.calls == []
    assert manager.broadcasts == []


async def test_worker_broadcasts_nothing_when_the_model_hears_only_noise():
    manager = FakeManager(["en"])
    translator = FakeTranslator(
        results=[
            TranslationResult("", {"en": "Fabricated text."}),
            TranslationResult("", {"en": "Fabricated text."}),
        ]
    )
    worker = make_worker(manager, translator)

    worker.process_audio_chunk(audio_chunk())
    await worker._flush_once()
    worker.process_audio_chunk(audio_chunk())
    await worker._flush_once()

    assert manager.broadcasts == []
    assert translator.calls[1][2] == ()


async def test_worker_passes_recent_transcript_as_context():
    manager = FakeManager(["en"])
    translator = FakeTranslator(
        results=[
            TranslationResult("神は愛です。", {"en": "God is love."}),
            TranslationResult("神は光です。", {"en": "God is light."}),
        ]
    )
    worker = make_worker(manager, translator)

    worker.process_audio_chunk(audio_chunk())
    await worker._flush_once()
    worker.process_audio_chunk(audio_chunk())
    await worker._flush_once()

    assert translator.calls[0][2] == ()
    assert translator.calls[1][2] == ("神は愛です。",)


async def test_worker_passes_the_church_glossary_to_every_request():
    glossary = parse_church_glossary(
        {
            "names": [{"japanese": "山田牧師", "en": "Pastor Yamada"}],
            "scripture": {"en": "NIV"},
        }
    )
    manager = FakeManager(["en"])
    translator = FakeTranslator(
        results=[
            TranslationResult("神は愛です。", {"en": "God is love."}),
            TranslationResult("神は光です。", {"en": "God is light."}),
        ]
    )
    worker = make_worker(manager, translator, glossary=glossary)

    worker.process_audio_chunk(audio_chunk())
    await worker._flush_once()
    worker.process_audio_chunk(audio_chunk())
    await worker._flush_once()

    assert [call[3] for call in translator.calls] == [glossary, glossary]


async def test_worker_uses_default_terminology_without_a_glossary():
    manager = FakeManager(["en"])
    translator = FakeTranslator()
    worker = make_worker(manager, translator)

    worker.process_audio_chunk(audio_chunk())
    await worker._flush_once()

    assert translator.calls[0][3] is None


async def test_worker_keeps_only_the_last_two_context_lines():
    manager = FakeManager(["en"])
    translator = FakeTranslator(
        results=[
            TranslationResult("一。", {"en": "One."}),
            TranslationResult("二。", {"en": "Two."}),
            TranslationResult("三。", {"en": "Three."}),
            TranslationResult("四。", {"en": "Four."}),
        ]
    )
    worker = make_worker(manager, translator)

    for _ in range(4):
        worker.process_audio_chunk(audio_chunk())
        await worker._flush_once()

    assert [call[2] for call in translator.calls] == [
        (),
        ("一。",),
        ("一。", "二。"),
        ("二。", "三。"),
    ]


async def test_worker_dedupes_overlap_before_broadcasting():
    manager = FakeManager(["en", "ko"])
    translator = FakeTranslator(
        results=[
            TranslationResult(
                "神は愛です。",
                {
                    "en": "God is love.",
                    "ko": "하나님은 사랑이십니다.",
                },
            ),
            TranslationResult(
                "神は愛です。神は光です。",
                {
                    "en": "God is love. God is light.",
                    "ko": "하나님은 사랑이십니다. 하나님은 빛이십니다.",
                },
            ),
        ]
    )
    worker = make_worker(manager, translator)

    worker.process_audio_chunk(audio_chunk())
    await worker._flush_once()
    worker.process_audio_chunk(audio_chunk())
    await worker._flush_once()

    assert [(item[0], item[1], item[3]) for item in manager.broadcasts] == [
        ("神は愛です。", "God is love.", "en"),
        ("神は愛です。", "하나님은 사랑이십니다.", "ko"),
        ("神は光です。", "God is light.", "en"),
        ("神は光です。", "하나님은 빛이십니다.", "ko"),
    ]


async def test_worker_skips_a_chunk_that_is_only_repeated_overlap():
    manager = FakeManager(["en"])
    translator = FakeTranslator(
        results=[
            TranslationResult("神は愛です。", {"en": "God is love."}),
            TranslationResult("神は愛です。", {"en": "God is love."}),
        ]
    )
    worker = make_worker(manager, translator)

    worker.process_audio_chunk(audio_chunk())
    await worker._flush_once()
    worker.process_audio_chunk(audio_chunk())
    await worker._flush_once()

    assert len(translator.calls) == 2
    assert [(item[0], item[1]) for item in manager.broadcasts] == [
        ("神は愛です。", "God is love."),
    ]
    assert translator.calls[1][2] == ("神は愛です。",)


async def test_worker_translates_a_multi_chunk_passage_with_shared_context():
    manager = FakeManager(["en"])
    translator = FakeTranslator(
        results=[
            TranslationResult("神は愛です。", {"en": "God is love."}),
            TranslationResult(
                "神は愛です。神は光です。",
                {"en": "God is love. God is light."},
            ),
            TranslationResult(
                "神は光です。私たちを導きます。",
                {"en": "God is light. He guides us."},
            ),
        ]
    )
    worker = make_worker(manager, translator)

    for _ in range(3):
        worker.process_audio_chunk(audio_chunk())
        await worker._flush_once()

    assert [call[2] for call in translator.calls] == [
        (),
        ("神は愛です。",),
        ("神は愛です。", "神は光です。"),
    ]
    assert [(item[0], item[1]) for item in manager.broadcasts] == [
        ("神は愛です。", "God is love."),
        ("神は光です。", "God is light."),
        ("私たちを導きます。", "He guides us."),
    ]


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
    assert worker.chunker.pending_new_bytes == int(32000 * 0.35)


async def test_worker_logs_transport_error_without_requeue(caplog):
    caplog.set_level(logging.WARNING, logger="app.gemini_worker")
    manager = FakeManager(["en"])
    translator = FakeTranslator(error=httpx.ReadTimeout("slow"))
    worker = make_worker(manager, translator)
    worker.process_audio_chunk(audio_chunk())

    await worker._flush_once()

    assert "gemini_transport_error" in caplog.text
    assert "神は愛です。" not in caplog.text
    assert worker.chunker.pending_new_bytes == int(32000 * 0.35)
