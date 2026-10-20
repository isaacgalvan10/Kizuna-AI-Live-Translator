import struct

from app.audio_chunking import AudioChunker, ChunkingConfig

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
BYTES_PER_SECOND = SAMPLE_RATE * SAMPLE_WIDTH


def pcm(seconds: float, amplitude: int) -> bytes:
    sample = struct.pack("<h", amplitude)
    return sample * int(SAMPLE_RATE * seconds)


def speech(seconds: float) -> bytes:
    return pcm(seconds, 2000)


def silence(seconds: float) -> bytes:
    return pcm(seconds, 0)


def make_chunker(**overrides) -> AudioChunker:
    config = ChunkingConfig(
        min_seconds=1.5,
        max_seconds=5.0,
        silence_seconds=0.35,
        overlap_seconds=0.3,
        **overrides,
    )
    return AudioChunker(config)


def test_holds_audio_until_the_minimum_duration():
    chunker = make_chunker()
    chunker.feed(speech(1.0))

    assert chunker.pop_ready() is None


def test_cuts_at_a_pause_once_the_minimum_is_reached():
    chunker = make_chunker()
    chunker.feed(speech(1.5) + silence(0.35))

    segment = chunker.pop_ready()

    assert segment is not None
    assert len(segment.pcm) == int(BYTES_PER_SECOND * 1.5)
    assert segment.overlap_bytes == 0


def test_cuts_at_the_maximum_when_speech_never_pauses():
    chunker = make_chunker()
    chunker.feed(speech(5.0))

    segment = chunker.pop_ready()

    assert segment is not None
    assert len(segment.pcm) == int(BYTES_PER_SECOND * 5.0)
    assert segment.overlap_bytes == 0


def test_prefers_a_short_pause_over_cutting_mid_speech_at_the_maximum():
    chunker = make_chunker()
    chunker.feed(speech(2.0) + silence(0.2) + speech(3.0))

    segment = chunker.pop_ready()

    assert segment is not None
    assert len(segment.pcm) == int(BYTES_PER_SECOND * 2.0)


def test_a_pause_that_starts_before_the_minimum_still_cuts_at_the_minimum():
    chunker = make_chunker()
    chunker.feed(speech(0.5) + silence(2.0))

    segment = chunker.pop_ready()

    assert segment is not None
    assert len(segment.pcm) == int(BYTES_PER_SECOND * 1.5)


def test_a_pause_split_across_feeds_is_still_detected():
    chunker = make_chunker()
    chunker.feed(speech(1.5))
    assert chunker.pop_ready() is None

    chunker.feed(silence(0.2))
    assert chunker.pop_ready() is None

    chunker.feed(silence(0.15))

    assert chunker.pop_ready() is not None


def test_the_next_chunk_starts_with_the_previous_tail():
    chunker = make_chunker()
    chunker.feed(speech(1.5) + silence(0.35))
    first = chunker.pop_ready()
    assert first is not None

    chunker.feed(speech(2.0) + silence(0.35))
    second = chunker.pop_ready()

    assert second is not None
    overlap_bytes = int(BYTES_PER_SECOND * 0.3)
    assert second.overlap_bytes == overlap_bytes
    assert second.pcm[:overlap_bytes] == first.pcm[-overlap_bytes:]


def test_silence_is_not_new_speech():
    chunker = make_chunker()
    chunker.feed(silence(1.85))

    segment = chunker.pop_ready()

    assert segment is not None
    assert chunker.contains_new_speech(segment) is False


def test_a_short_blip_is_not_new_speech():
    chunker = make_chunker()
    chunker.feed(speech(0.1) + silence(1.75))

    segment = chunker.pop_ready()

    assert segment is not None
    assert chunker.contains_new_speech(segment) is False


def test_repeated_overlap_does_not_count_as_new_speech():
    chunker = make_chunker()
    chunker.feed(speech(1.5) + silence(0.35))
    first = chunker.pop_ready()
    assert first is not None

    chunker.feed(silence(5.0))
    segment = chunker.pop_ready()

    assert segment is not None
    assert segment.overlap_bytes > 0
    assert chunker.contains_new_speech(segment) is False


def test_clearing_resets_the_buffer_and_overlap():
    chunker = make_chunker()
    chunker.feed(speech(1.5) + silence(0.35))
    assert chunker.pop_ready() is not None

    chunker.clear()
    chunker.feed(speech(1.5) + silence(0.35))
    segment = chunker.pop_ready()

    assert segment is not None
    assert segment.overlap_bytes == 0
    assert chunker.pending_new_bytes == int(BYTES_PER_SECOND * 0.35)
