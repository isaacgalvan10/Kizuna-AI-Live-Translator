import asyncio
import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from fastapi import WebSocket

if TYPE_CHECKING:
    from .church_glossary import ChurchGlossary

logger = logging.getLogger(__name__)

FeedState = Literal["live", "paused", "stopped"]
FEED_STATE_LIVE: FeedState = "live"
FEED_STATE_PAUSED: FeedState = "paused"
FEED_STATE_STOPPED: FeedState = "stopped"

# The channel the operator console subscribes to for feed lifecycle events.
# It is not a guest language, so it must never be treated as a translation target.
OPERATOR_CHANNEL = "operator"

BACKFILL_WINDOW_SECONDS = 3 * 60
BACKFILL_MAX_LINES = 25


@dataclass(frozen=True)
class TranscriptLine:
    japanese: str
    created_at: float


def select_backfill_lines(
    lines: Sequence[TranscriptLine],
    now: float,
    *,
    window_seconds: float = BACKFILL_WINDOW_SECONDS,
    max_lines: int = BACKFILL_MAX_LINES,
) -> list[TranscriptLine]:
    """Returns the recent transcript lines a new language channel can catch up on."""
    if not lines:
        return []

    cutoff = now - window_seconds
    recent = [line for line in lines if line.created_at >= cutoff]
    return recent[-max_lines:]


class ConnectionManager:
    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        backfill_translator=None,
    ):
        self.active_connections: dict[str, dict[str, list[WebSocket]]] = {}
        self.history_buffer: dict[str, dict[str, list[dict]]] = {}
        self.timeline: dict[str, list[TranscriptLine]] = {}
        self.backfill_translator = backfill_translator
        self._clock = clock or time.monotonic
        self._syncing: set[WebSocket] = set()
        self._history_locks: dict[str, asyncio.Lock] = {}

    def reset(self) -> None:
        self.active_connections.clear()
        self.history_buffer.clear()
        self.timeline.clear()
        self._syncing.clear()
        self._history_locks.clear()

    def get_active_languages(self, room_id: str) -> list[str]:
        """Returns a list of language codes that currently have active listeners."""
        if room_id not in self.active_connections:
            return []

        active_langs = []
        for lang, websockets in self.active_connections[room_id].items():
            if lang == OPERATOR_CHANNEL:
                continue
            if len(websockets) > 0:
                active_langs.append(lang)
        return active_langs

    def record_transcript(self, room_id: str, japanese: str) -> None:
        """Adds one cleaned Japanese line to the current Live Feed's timeline."""
        text = japanese.strip()
        if not text:
            return
        self.timeline.setdefault(room_id, []).append(
            TranscriptLine(japanese=text, created_at=self._clock())
        )

    async def connect(
        self,
        websocket: WebSocket,
        room_id: str,
        language: str,
        *,
        glossary: "ChurchGlossary | None" = None,
    ):
        await websocket.accept()

        # Safe initialization using setdefault: Never overwrites existing keys
        self.active_connections.setdefault(room_id, {})
        self.active_connections[room_id].setdefault(language, [])
        self.active_connections[room_id][language].append(websocket)

        self.history_buffer.setdefault(room_id, {})
        self.history_buffer[room_id].setdefault(language, [])

        if language == OPERATOR_CHANNEL:
            return

        # A joining listener receives history before any live line for that
        # channel. While it is syncing, broadcasts keep appending to the shared
        # history but skip this socket; the snapshot loop below catches up.
        self._syncing.add(websocket)
        try:
            await self._deliver_history(
                websocket,
                room_id,
                language,
                glossary,
            )
        except Exception:
            self.disconnect(websocket, room_id, language)
            raise
        finally:
            self._syncing.discard(websocket)

    async def _deliver_history(
        self,
        websocket: WebSocket,
        room_id: str,
        language: str,
        glossary: "ChurchGlossary | None",
    ) -> None:
        async with self._history_lock(room_id):
            history = self.history_buffer.setdefault(
                room_id, {}
            ).setdefault(language, [])
            if not history:
                await self._backfill(room_id, language, glossary)
            await self._send_history_until_stable(
                websocket,
                room_id,
                language,
            )

    async def _send_history_until_stable(
        self,
        websocket: WebSocket,
        room_id: str,
        language: str,
    ) -> None:
        sent = 0
        while True:
            history = self.history_buffer.get(room_id, {}).get(language, [])
            if sent >= len(history):
                return
            snapshot = list(history)
            await websocket.send_text(
                json.dumps({"type": "history", "data": snapshot})
            )
            sent = len(snapshot)

    async def _backfill(
        self,
        room_id: str,
        language: str,
        glossary: "ChurchGlossary | None",
    ) -> None:
        lines = select_backfill_lines(
            self.timeline.get(room_id, []),
            self._clock(),
        )
        if not lines:
            return

        translator = self._get_backfill_translator()
        try:
            result = await translator.translate_lines(
                [line.japanese for line in lines],
                [language],
                glossary=glossary,
            )
        except Exception as exc:
            # Backfill is best-effort: the listener can still follow the live
            # feed. Log only metadata, never the sermon text.
            logger.warning(
                "history_backfill_failed room_id=%s language=%s error=%s",
                room_id,
                language,
                type(exc).__name__,
            )
            return

        translations = result.translations.get(language, [])
        entries = [
            {"original": line.japanese, "translation": translation}
            for line, translation in zip(lines, translations)
            if translation.strip()
        ]
        if not entries:
            return

        self.history_buffer.setdefault(room_id, {}).setdefault(
            language, []
        )[0:0] = entries
        logger.info(
            "history_backfilled room_id=%s language=%s lines=%d",
            room_id,
            language,
            len(entries),
        )

    def _get_backfill_translator(self):
        if self.backfill_translator is None:
            from .gemini_translation import GeminiTranslator

            self.backfill_translator = GeminiTranslator()
        return self.backfill_translator

    def _history_lock(self, room_id: str) -> asyncio.Lock:
        lock = self._history_locks.get(room_id)
        if lock is None:
            lock = asyncio.Lock()
            self._history_locks[room_id] = lock
        return lock

    def disconnect(self, websocket: WebSocket, room_id: str, language: str):
        self._syncing.discard(websocket)
        if room_id in self.active_connections and language in self.active_connections[room_id]:
            # Added a safe check to see if the websocket is actually still in the list
            if websocket in self.active_connections[room_id][language]:
                self.active_connections[room_id][language].remove(websocket)

            # Clean up empty dictionaries to save server memory
            if not self.active_connections[room_id][language]:
                del self.active_connections[room_id][language]

    async def broadcast_to_language(self, original: str, translation: str, room_id: str, language: str):
        message_obj = {"original": original, "translation": translation}

        # Always secure the history state safely
        self.history_buffer.setdefault(room_id, {})
        self.history_buffer[room_id].setdefault(language, [])
        self.history_buffer[room_id][language].append(message_obj)

        if room_id in self.active_connections and language in self.active_connections[room_id]:
            payload = json.dumps({"type": "live_translation", "data": message_obj})
            dead_connections = []

            for connection in list(self.active_connections[room_id][language]):
                if connection in self._syncing:
                    continue
                try:
                    await connection.send_text(payload)
                except Exception:
                    dead_connections.append(connection)

            for dead in dead_connections:
                self.disconnect(dead, room_id, language)

    async def clear_history(self, room_id: str) -> None:
        """Clears the current Live Feed's timeline and every channel history."""
        async with self._history_lock(room_id):
            had_history = bool(self.timeline.get(room_id)) or any(
                self.history_buffer.get(room_id, {}).values()
            )
            self.timeline.pop(room_id, None)
            self.history_buffer.pop(room_id, None)

            if not had_history:
                return

            payload = json.dumps({"type": "history", "data": []})
            for language in list(self.active_connections.get(room_id, {})):
                if language == OPERATOR_CHANNEL:
                    continue
                dead_connections = []
                for connection in list(
                    self.active_connections[room_id][language]
                ):
                    try:
                        await connection.send_text(payload)
                    except Exception:
                        dead_connections.append(connection)

                for dead in dead_connections:
                    self.disconnect(dead, room_id, language)

    async def broadcast_feed_state(self, room_id: str, state: FeedState):
        """Sends a feed lifecycle event to every listener in the room, across all languages."""
        if room_id not in self.active_connections:
            return

        payload = json.dumps({"type": "feed_state", "data": state})

        for language in list(self.active_connections[room_id].keys()):
            dead_connections = []

            for connection in self.active_connections[room_id][language]:
                try:
                    await connection.send_text(payload)
                except Exception:
                    dead_connections.append(connection)

            for dead in dead_connections:
                self.disconnect(dead, room_id, language)

    async def broadcast_interim(self, original: str, translation: str, room_id: str, language: str):
        if room_id in self.active_connections and language in self.active_connections[room_id]:
            payload = json.dumps({
                "type": "interim_translation",
                "data": {"original": original, "translation": translation}
            })
            dead_connections = []

            for connection in self.active_connections[room_id][language]:
                try:
                    await connection.send_text(payload)
                except Exception:
                    dead_connections.append(connection)

            for dead in dead_connections:
                self.disconnect(dead, room_id, language)


manager = ConnectionManager()
