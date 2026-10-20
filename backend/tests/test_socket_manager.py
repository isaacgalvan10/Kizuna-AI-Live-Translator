import json

import pytest

from app.socket_manager import manager


class FakeWebSocket:
    def __init__(self):
        self.sent: list[str] = []

    async def accept(self):
        pass

    async def send_text(self, text: str):
        self.sent.append(text)


@pytest.fixture(autouse=True)
def clean_socket_manager():
    manager.active_connections.clear()
    manager.history_buffer.clear()
    yield
    manager.active_connections.clear()
    manager.history_buffer.clear()


async def test_operator_channel_does_not_count_as_a_translation_target():
    from app.socket_manager import OPERATOR_CHANNEL

    operator_socket = FakeWebSocket()
    listener_socket = FakeWebSocket()
    await manager.connect(operator_socket, "77", OPERATOR_CHANNEL)
    await manager.connect(listener_socket, "77", "en")

    assert manager.get_active_languages("77") == ["en"]


async def test_feed_state_still_reaches_the_operator_channel():
    from app.socket_manager import FEED_STATE_PAUSED, OPERATOR_CHANNEL

    operator_socket = FakeWebSocket()
    await manager.connect(operator_socket, "77", OPERATOR_CHANNEL)

    await manager.broadcast_feed_state("77", FEED_STATE_PAUSED)

    messages = [json.loads(raw) for raw in operator_socket.sent]
    assert {"type": "feed_state", "data": "paused"} in messages


async def test_a_translation_reaches_every_listener_in_the_language_channel():
    first_listener = FakeWebSocket()
    second_listener = FakeWebSocket()
    await manager.connect(first_listener, "88", "en")
    await manager.connect(second_listener, "88", "en")

    await manager.broadcast_to_language("神は愛です。", "God is love.", "88", "en")

    expected = json.dumps(
        {
            "type": "live_translation",
            "data": {
                "original": "神は愛です。",
                "translation": "God is love.",
            },
        }
    )
    assert first_listener.sent == [expected]
    assert second_listener.sent == [expected]
