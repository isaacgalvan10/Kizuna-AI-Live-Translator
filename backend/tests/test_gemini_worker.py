import asyncio
from unittest.mock import AsyncMock

import pytest

import app.gemini_worker as gemini_worker_module
from app.gemini_worker import GeminiWorker


def pcm_constant(value: int, seconds: float = 2.0) -> bytes:
    """Constant-amplitude 16-bit PCM: RMS equals abs(value)."""
    frames = int(16000 * seconds)
    return value.to_bytes(2, "little", signed=True) * frames


class StubManager:
    def __init__(self, langs):
        self.langs = langs
        self.broadcasts = []

    def get_active_languages(self, room_id):
        return self.langs

    async def broadcast_to_language(self, original, translation, room_id, language):
        self.broadcasts.append((original, translation, room_id, language))


class FakeGeminiResponse:
    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        pass

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self._text}]}}]}


def gemini_replies(text: str) -> AsyncMock:
    post = AsyncMock(return_value=FakeGeminiResponse(text))
    return post


@pytest.fixture
def stub_manager(monkeypatch):
    stub = StubManager(["en", "ko"])
    monkeypatch.setattr(gemini_worker_module, "manager", stub)
    return stub


@pytest.fixture
async def worker():
    instance = GeminiWorker("1", asyncio.get_running_loop())
    instance.http_client = AsyncMock()
    yield instance
    instance.stop()
    await asyncio.sleep(0)


async def test_silent_audio_never_reaches_gemini(worker, stub_manager):
    """A digitally-silent chunk is dropped; Gemini is never asked, nothing is broadcast."""
    worker.process_audio_chunk(pcm_constant(0))

    await worker._flush_cycle()

    worker.http_client.post.assert_not_awaited()
    assert stub_manager.broadcasts == []


async def test_room_noise_below_threshold_never_reaches_gemini(worker, stub_manager):
    """Low-level room tone is below the loudness gate: no API call, nothing broadcast."""
    worker.process_audio_chunk(pcm_constant(120))

    await worker._flush_cycle()

    worker.http_client.post.assert_not_awaited()
    assert stub_manager.broadcasts == []


async def test_speech_level_audio_calls_gemini_and_broadcasts_each_language(worker, stub_manager):
    worker.process_audio_chunk(pcm_constant(3000))
    worker.http_client.post = gemini_replies("[JA] 今日はよい日です\n[EN] Today is a good day\n[KO] 오늘은 좋은 날입니다")

    await worker._flush_cycle()

    worker.http_client.post.assert_awaited_once()
    sent_prompt = worker.http_client.post.await_args.kwargs["json"]["systemInstruction"]["parts"][0]["text"]
    assert "HALLUCINATION GUARD" in sent_prompt
    assert stub_manager.broadcasts == [
        ("今日はよい日です", "Today is a good day", "1", "en"),
        ("今日はよい日です", "오늘은 좋은 날입니다", "1", "ko"),
    ]


async def test_gemini_silence_marker_is_not_broadcast(worker, stub_manager):
    """Even when audio passes the gate, a 'nothing was said' answer must not reach listeners."""
    worker.process_audio_chunk(pcm_constant(3000))
    worker.http_client.post = gemini_replies("[JA] SILENCE\n[EN] Silence")

    await worker._flush_cycle()

    worker.http_client.post.assert_awaited_once()
    assert stub_manager.broadcasts == []


async def test_bare_silence_marker_is_not_broadcast(worker, stub_manager):
    worker.process_audio_chunk(pcm_constant(3000))
    worker.http_client.post = gemini_replies("[SILENCE]")

    await worker._flush_cycle()

    assert stub_manager.broadcasts == []


async def test_no_listeners_clears_buffer_without_calling_gemini(worker, stub_manager):
    stub_manager.langs = []
    worker.process_audio_chunk(pcm_constant(3000))

    await worker._flush_cycle()

    worker.http_client.post.assert_not_awaited()
    assert len(worker.audio_buffer) == 0


async def test_short_buffer_is_kept_for_the_next_cycle(worker, stub_manager):
    chunk = pcm_constant(3000, seconds=0.1)
    worker.process_audio_chunk(chunk)

    await worker._flush_cycle()

    worker.http_client.post.assert_not_awaited()
    assert len(worker.audio_buffer) == len(chunk)


@pytest.mark.parametrize(
    "text",
    ["SILENCE", "[SILENCE]", "(silence)", "silence.", "No speech", "no audible speech", " [SILENCE] "],
)
async def test_silence_marker_variants_are_recognized(worker, text):
    assert worker._is_silence_marker(text)


@pytest.mark.parametrize("text", ["silent prayer", "無音", ""])
async def test_normal_transcriptions_are_not_silence_markers(worker, text):
    assert not worker._is_silence_marker(text)
