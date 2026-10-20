import struct
from dataclasses import dataclass

SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2
CHANNELS = 1
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * SAMPLE_WIDTH * CHANNELS


def seconds_to_bytes(seconds: float) -> int:
    return int(SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS * seconds)


@dataclass(frozen=True)
class ChunkingConfig:
    min_seconds: float = 1.5
    max_seconds: float = 5.0
    silence_seconds: float = 0.35
    short_pause_seconds: float = 0.15
    overlap_seconds: float = 0.3
    silence_rms: int = 300
    min_speech_seconds: float = 0.2


@dataclass(frozen=True)
class AudioSegment:
    pcm: bytes
    overlap_bytes: int = 0


class AudioChunker:
    """Buffers PCM and emits chunks at pauses (sentence boundaries) or the cap.

    A pause is a run of silent 20 ms frames. When a pause is found after the
    minimum duration, the chunk is cut at the start of that pause so the
    translation ends on a natural boundary. The next chunk starts with a short
    overlap from the previous tail so the model does not lose the first word;
    callers deduplicate the resulting text.
    """

    def __init__(self, config: ChunkingConfig | None = None):
        self.config = config or ChunkingConfig()
        config = self.config
        if config.min_seconds <= 0:
            raise ValueError("min_seconds must be positive")
        if config.max_seconds < config.min_seconds:
            raise ValueError("max_seconds must be at least min_seconds")
        if config.overlap_seconds < 0:
            raise ValueError("overlap_seconds cannot be negative")

        self.min_bytes = seconds_to_bytes(config.min_seconds)
        self.max_bytes = seconds_to_bytes(config.max_seconds)
        self.overlap_bytes = seconds_to_bytes(config.overlap_seconds)
        self._min_speech_bytes = seconds_to_bytes(config.min_speech_seconds)
        self._silence_frames = max(
            1,
            int(config.silence_seconds * 1000 / FRAME_MS),
        )
        self._short_pause_frames = max(
            1,
            int(config.short_pause_seconds * 1000 / FRAME_MS),
        )
        self._silence_energy_limit = (
            config.silence_rms * config.silence_rms * FRAME_SAMPLES
        )

        self.buffer = bytearray()
        self._pending_overlap = 0

    @property
    def pending_new_bytes(self) -> int:
        return max(0, len(self.buffer) - self._pending_overlap)

    def feed(self, pcm: bytes) -> None:
        self.buffer.extend(pcm)

    def clear(self) -> None:
        self.buffer.clear()
        self._pending_overlap = 0

    def pop_ready(self) -> AudioSegment | None:
        if len(self.buffer) < self.min_bytes:
            return None

        cut = self._first_pause_cut(self._silence_frames)
        if cut is None:
            if len(self.buffer) < self.max_bytes:
                return None
            cut = self._latest_pause_cut(self._short_pause_frames)
            if cut is None:
                cut = self.max_bytes

        chunk = bytes(self.buffer[:cut])
        del self.buffer[:cut]

        overlap = min(self.overlap_bytes, len(chunk))
        if overlap:
            self.buffer[:0] = chunk[-overlap:]
        incoming_overlap = min(self._pending_overlap, len(chunk))
        self._pending_overlap = overlap

        return AudioSegment(pcm=chunk, overlap_bytes=incoming_overlap)

    def contains_new_speech(self, segment: AudioSegment) -> bool:
        """Reports whether the segment has enough new speech to translate.

        The leading overlap was already translated as part of the previous
        chunk, so it is ignored. Short blips and silence stay below the
        minimum speech duration and are never sent to the model.
        """

        data = segment.pcm[segment.overlap_bytes :]
        speech_bytes = 0
        for _, frame in self._iter_frames(data):
            if not self._is_silent(frame):
                speech_bytes += FRAME_BYTES
                if speech_bytes >= self._min_speech_bytes:
                    return True
        return self._min_speech_bytes == 0

    def _first_pause_cut(self, min_pause_frames: int) -> int | None:
        pause_start: int | None = None
        pause_frames = 0

        for offset, frame in self._iter_frames(self.buffer, self.max_bytes):
            if self._is_silent(frame):
                if pause_start is None:
                    pause_start = offset
                pause_frames += 1
                pause_end = offset + FRAME_BYTES
                if pause_frames >= min_pause_frames and pause_end > self.min_bytes:
                    return max(pause_start, self.min_bytes)
            else:
                pause_start = None
                pause_frames = 0
        return None

    def _latest_pause_cut(self, min_pause_frames: int) -> int | None:
        pause_start: int | None = None
        pause_frames = 0
        latest: int | None = None

        for offset, frame in self._iter_frames(self.buffer, self.max_bytes):
            if self._is_silent(frame):
                if pause_start is None:
                    pause_start = offset
                pause_frames += 1
                pause_end = offset + FRAME_BYTES
                if pause_frames >= min_pause_frames and pause_end > self.min_bytes:
                    latest = max(pause_start, self.min_bytes)
            else:
                pause_start = None
                pause_frames = 0
        return latest

    def _iter_frames(self, data, limit: int | None = None):
        end = len(data) if limit is None else min(len(data), limit)
        for offset in range(0, end - FRAME_BYTES + 1, FRAME_BYTES):
            yield offset, data[offset : offset + FRAME_BYTES]

    def _is_silent(self, frame) -> bool:
        energy = 0
        for (sample,) in struct.iter_unpack("<h", frame):
            energy += sample * sample
        return energy <= self._silence_energy_limit
