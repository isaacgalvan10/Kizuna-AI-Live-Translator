import asyncio
import json

import pytest

from app.socket_manager import ConnectionManager


class FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.sent: list[str] = []

    async def accept(self):
        self.accepted = True

    async def send_text(self, text: str):
        self.sent.append(text)

    def messages(self) -> list[dict]:
        return [json.loads(raw) for raw in self.sent]

    def history(self) -> list[dict]:
        return [
            message["data"]
            for message in self.messages()
            if message["type"] == "history"
        ]


class FakeBackfillTranslator:
    def __init__(self, translations=None, error=None):
        self.translations = translations or {}
        self.error = error
        self.calls: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    async def translate_lines(self, lines, active_languages, *, glossary=None):
        self.calls.append((tuple(lines), tuple(active_languages)))
        if self.error is not None:
            raise self.error

        return type(
            "BackfillResult",
            (),
            {
                "translations": {
                    code: self.translations.get(code, list(lines))
                    for code in active_languages
                }
            },
        )()


@pytest.fixture
def manager():
    return ConnectionManager()


async def test_a_new_channel_is_backfilled_in_one_batch_call(manager):
    translator = FakeBackfillTranslator(
        translations={
            "ko": ["하나님은 사랑이십니다.", "하나님은 빛이십니다."],
        }
    )
    manager.backfill_translator = translator

    english_listener = FakeWebSocket()
    await manager.connect(english_listener, "room-1", "en")
    manager.record_transcript("room-1", "神は愛です。")
    await manager.broadcast_to_language(
        "神は愛です。",
        "God is love.",
        "room-1",
        "en",
    )
    manager.record_transcript("room-1", "神は光です。")
    await manager.broadcast_to_language(
        "神は光です。",
        "God is light.",
        "room-1",
        "en",
    )

    korean_listener = FakeWebSocket()
    await manager.connect(korean_listener, "room-1", "ko")

    assert translator.calls == [
        (("神は愛です。", "神は光です。"), ("ko",)),
    ]
    assert korean_listener.history() == [
        [
            {
                "original": "神は愛です。",
                "translation": "하나님은 사랑이십니다.",
            },
            {
                "original": "神は光です。",
                "translation": "하나님은 빛이십니다.",
            },
        ]
    ]


async def test_backfill_covers_only_the_last_three_minutes():
    clock = [0.0]
    translator = FakeBackfillTranslator()
    manager = ConnectionManager(
        clock=lambda: clock[0],
        backfill_translator=translator,
    )
    await manager.connect(FakeWebSocket(), "room-1", "en")

    for timestamp, japanese in [
        (0.0, "古い一。"),
        (60.0, "古い二。"),
        (130.0, "最近一。"),
        (200.0, "最近二。"),
        (300.0, "最近三。"),
    ]:
        clock[0] = timestamp
        manager.record_transcript("room-1", japanese)

    clock[0] = 300.0
    await manager.connect(FakeWebSocket(), "room-1", "ko")

    assert translator.calls == [
        (("最近一。", "最近二。", "最近三。"), ("ko",)),
    ]


async def test_backfill_is_capped_at_twenty_five_lines():
    translator = FakeBackfillTranslator()
    manager = ConnectionManager(
        clock=lambda: 1000.0,
        backfill_translator=translator,
    )
    await manager.connect(FakeWebSocket(), "room-1", "en")

    for number in range(30):
        manager.record_transcript("room-1", f"行{number}。")

    await manager.connect(FakeWebSocket(), "room-1", "ko")

    assert translator.calls[0][0] == tuple(
        f"行{number}。" for number in range(5, 30)
    )


class BlockingBackfillTranslator(FakeBackfillTranslator):
    def __init__(self, translations=None):
        super().__init__(translations=translations)
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def translate_lines(self, lines, active_languages, *, glossary=None):
        self.calls.append((tuple(lines), tuple(active_languages)))
        self.started.set()
        await self.release.wait()
        return type(
            "BackfillResult",
            (),
            {
                "translations": {
                    code: self.translations.get(code, list(lines))
                    for code in active_languages
                }
            },
        )()


async def test_concurrent_joins_to_a_new_channel_backfill_once():
    translator = BlockingBackfillTranslator(
        translations={"ko": ["하나님은 사랑이십니다."]},
    )
    manager = ConnectionManager(backfill_translator=translator)
    manager.record_transcript("room-1", "神は愛です。")

    first = FakeWebSocket()
    second = FakeWebSocket()
    first_join = asyncio.create_task(
        manager.connect(first, "room-1", "ko")
    )
    await translator.started.wait()

    second_join = asyncio.create_task(
        manager.connect(second, "room-1", "ko")
    )
    translator.release.set()
    await asyncio.gather(first_join, second_join)

    assert len(translator.calls) == 1
    expected = [
        [
            {
                "original": "神は愛です。",
                "translation": "하나님은 사랑이십니다.",
            }
        ]
    ]
    assert first.history() == expected
    assert second.history() == expected


async def test_a_listener_joining_an_existing_channel_gets_that_channel_history(
    manager,
):
    first = FakeWebSocket()
    await manager.connect(first, "room-1", "en")
    manager.record_transcript("room-1", "神は愛です。")
    await manager.broadcast_to_language(
        "神は愛です。",
        "God is love.",
        "room-1",
        "en",
    )

    late = FakeWebSocket()
    await manager.connect(late, "room-1", "en")

    assert late.history() == [
        [
            {"original": "神は愛です。", "translation": "God is love."},
        ]
    ]


async def test_reconnecting_to_a_channel_keeps_its_history_without_backfilling(
    manager,
):
    translator = FakeBackfillTranslator()
    manager.backfill_translator = translator
    listener = FakeWebSocket()
    await manager.connect(listener, "room-1", "en")
    manager.record_transcript("room-1", "神は愛です。")
    await manager.broadcast_to_language(
        "神は愛です。",
        "God is love.",
        "room-1",
        "en",
    )
    manager.disconnect(listener, "room-1", "en")

    reconnected = FakeWebSocket()
    await manager.connect(reconnected, "room-1", "en")

    assert translator.calls == []
    assert reconnected.history() == [
        [
            {"original": "神は愛です。", "translation": "God is love."},
        ]
    ]


async def test_an_empty_feed_does_not_call_the_backfill_api(manager):
    translator = FakeBackfillTranslator()
    manager.backfill_translator = translator

    listener = FakeWebSocket()
    await manager.connect(listener, "room-1", "en")

    assert translator.calls == []
    assert listener.sent == []


async def test_a_failed_backfill_does_not_drop_the_listener(manager):
    translator = FakeBackfillTranslator(error=RuntimeError("upstream down"))
    manager.backfill_translator = translator
    manager.record_transcript("room-1", "神は愛です。")

    listener = FakeWebSocket()
    await manager.connect(listener, "room-1", "ko")

    assert listener.history() == []
    assert manager.get_active_languages("room-1") == ["ko"]


async def test_the_operator_channel_never_receives_listener_history(manager):
    manager.record_transcript("room-1", "神は愛です。")
    await manager.broadcast_to_language(
        "神は愛です。",
        "God is love.",
        "room-1",
        "en",
    )

    operator = FakeWebSocket()
    await manager.connect(operator, "room-1", "operator")

    assert operator.sent == []


async def test_clear_history_notifies_listeners_and_starts_a_fresh_timeline(
    manager,
):
    english_listener = FakeWebSocket()
    await manager.connect(english_listener, "room-1", "en")
    manager.record_transcript("room-1", "神は愛です。")
    await manager.broadcast_to_language(
        "神は愛です。",
        "God is love.",
        "room-1",
        "en",
    )

    await manager.clear_history("room-1")

    assert english_listener.messages()[-1] == {"type": "history", "data": []}
    assert manager.timeline.get("room-1") is None

    late = FakeWebSocket()
    await manager.connect(late, "room-1", "en")
    assert late.history() == []


async def test_a_live_line_during_backfill_is_included_once_in_history():
    translator = BlockingBackfillTranslator(
        translations={"ko": ["하나님은 사랑이십니다."]},
    )
    manager = ConnectionManager(backfill_translator=translator)
    manager.record_transcript("room-1", "神は愛です。")

    listener = FakeWebSocket()
    join = asyncio.create_task(manager.connect(listener, "room-1", "ko"))
    await translator.started.wait()

    manager.record_transcript("room-1", "神は光です。")
    await manager.broadcast_to_language(
        "神は光です。",
        "하나님은 빛이십니다.",
        "room-1",
        "ko",
    )
    translator.release.set()
    await join

    assert listener.history() == [
        [
            {
                "original": "神は愛です。",
                "translation": "하나님은 사랑이십니다.",
            },
            {
                "original": "神は光です。",
                "translation": "하나님은 빛이십니다.",
            },
        ]
    ]
