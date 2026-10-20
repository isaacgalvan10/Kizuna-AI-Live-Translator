import json

import pytest

from app.auth import hash_password
from app.models import Church, Room, User
from app.socket_manager import manager


class FakeWebSocket:
    """Stands in for a Starlette WebSocket so tests can observe what the manager sends."""

    def __init__(self):
        self.accepted = False
        self.sent: list[str] = []

    async def accept(self):
        self.accepted = True

    async def send_text(self, text: str):
        self.sent.append(text)


def sent_feed_states(websocket: FakeWebSocket) -> list[str]:
    messages = [json.loads(raw) for raw in websocket.sent]
    return [message["data"] for message in messages if message["type"] == "feed_state"]


@pytest.fixture(autouse=True)
def clean_socket_manager():
    manager.reset()
    yield
    manager.reset()


@pytest.fixture
async def room(db_session, operator_setup):
    room = Room(church_id=operator_setup["church"].id, is_live=False)
    db_session.add(room)
    await db_session.commit()
    await db_session.refresh(room)
    return room


@pytest.fixture
async def other_church_operator(client, db_session):
    church = Church(name="Second Church", qr_code_hash="second-hash-456")
    db_session.add(church)
    await db_session.commit()
    await db_session.refresh(church)

    password = "second-church-password"
    operator = User(
        email="operator@second.church",
        hashed_password=hash_password(password),
        is_guest=False,
        church_id=church.id,
    )
    db_session.add(operator)
    await db_session.commit()

    login = await client.post(
        "/api/operator/login",
        json={"email": operator.email, "password": password},
    )
    return {
        "church": church,
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


@pytest.mark.parametrize("action", ["start", "pause", "stop"])
async def test_feed_control_requires_operator_token(client, room, action):
    response = await client.post(f"/api/operator/rooms/{room.id}/{action}")

    assert response.status_code == 401


async def test_start_marks_the_room_live(client, room, auth_headers, db_session):
    headers = await auth_headers()

    response = await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "live"}

    await db_session.refresh(room)
    assert room.is_live is True


async def test_start_rejects_unknown_room(client, auth_headers):
    headers = await auth_headers()

    response = await client.post("/api/operator/rooms/9999/start", headers=headers)

    assert response.status_code == 404


@pytest.mark.parametrize("action", ["start", "pause", "stop"])
async def test_operator_cannot_control_another_churchs_room(
    client, room, other_church_operator, db_session, action
):
    response = await client.post(
        f"/api/operator/rooms/{room.id}/{action}", headers=other_church_operator["headers"]
    )

    assert response.status_code == 404

    await db_session.refresh(room)
    assert room.is_live is False


async def test_start_is_idempotent_when_room_already_live(client, room, auth_headers, db_session):
    headers = await auth_headers()

    first = await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)
    second = await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == {"status": "live"}

    await db_session.refresh(room)
    assert room.is_live is True


async def test_start_broadcasts_live_to_every_language_channel(client, room, auth_headers):
    english_listener = FakeWebSocket()
    korean_listener = FakeWebSocket()
    await manager.connect(english_listener, str(room.id), "en")
    await manager.connect(korean_listener, str(room.id), "ko")

    headers = await auth_headers()
    await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)

    assert sent_feed_states(english_listener) == ["live"]
    assert sent_feed_states(korean_listener) == ["live"]


async def test_feed_state_broadcast_does_not_reach_other_rooms(
    client, room, auth_headers, operator_setup, db_session
):
    other_room = Room(church_id=operator_setup["church"].id, is_live=False)
    db_session.add(other_room)
    await db_session.commit()
    await db_session.refresh(other_room)

    bystander = FakeWebSocket()
    await manager.connect(bystander, str(other_room.id), "en")

    headers = await auth_headers()
    await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)

    assert sent_feed_states(bystander) == []


async def test_start_succeeds_with_no_listeners_connected(client, room, auth_headers):
    headers = await auth_headers()

    response = await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)

    assert response.status_code == 200


async def test_pause_reports_paused_and_keeps_room_findable(
    client, room, auth_headers, db_session
):
    headers = await auth_headers()
    await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)

    response = await client.post(f"/api/operator/rooms/{room.id}/pause", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "paused"}

    await db_session.refresh(room)
    assert room.is_live is True


async def test_pause_broadcasts_paused_to_listeners(client, room, auth_headers):
    headers = await auth_headers()
    await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)

    listener = FakeWebSocket()
    await manager.connect(listener, str(room.id), "en")

    await client.post(f"/api/operator/rooms/{room.id}/pause", headers=headers)

    assert sent_feed_states(listener) == ["paused"]


async def test_a_fresh_start_clears_the_previous_feed_history(
    client, room, auth_headers
):
    listener = FakeWebSocket()
    await manager.connect(listener, str(room.id), "en")
    manager.record_transcript(str(room.id), "前の礼拝。")
    await manager.broadcast_to_language(
        "前の礼拝。",
        "Last service.",
        str(room.id),
        "en",
    )
    listener.sent.clear()

    headers = await auth_headers()
    await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)

    assert [message["type"] for message in map(json.loads, listener.sent)] == [
        "history",
        "feed_state",
    ]
    assert listener.sent[0] == json.dumps({"type": "history", "data": []})
    assert manager.timeline.get(str(room.id)) is None


async def test_resuming_after_pause_keeps_the_feed_history(
    client, room, auth_headers
):
    headers = await auth_headers()
    await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)

    listener = FakeWebSocket()
    await manager.connect(listener, str(room.id), "en")
    manager.record_transcript(str(room.id), "続きの礼拝。")
    await manager.broadcast_to_language(
        "続きの礼拝。",
        "The service continues.",
        str(room.id),
        "en",
    )
    await client.post(f"/api/operator/rooms/{room.id}/pause", headers=headers)

    listener.sent.clear()
    await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)

    assert [json.loads(raw) for raw in listener.sent] == [
        {"type": "feed_state", "data": "live"},
    ]
    assert manager.timeline.get(str(room.id)) is not None


async def test_start_after_pause_resumes_the_feed(client, room, auth_headers):
    headers = await auth_headers()
    await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)
    await client.post(f"/api/operator/rooms/{room.id}/pause", headers=headers)

    listener = FakeWebSocket()
    await manager.connect(listener, str(room.id), "en")

    response = await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "live"}
    assert sent_feed_states(listener) == ["live"]


async def test_stop_marks_the_room_not_live(client, room, auth_headers, db_session):
    headers = await auth_headers()
    await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)

    response = await client.post(f"/api/operator/rooms/{room.id}/stop", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "stopped"}

    await db_session.refresh(room)
    assert room.is_live is False


async def test_stop_broadcasts_stopped_to_listeners(client, room, auth_headers):
    headers = await auth_headers()
    await client.post(f"/api/operator/rooms/{room.id}/start", headers=headers)

    listener = FakeWebSocket()
    await manager.connect(listener, str(room.id), "en")

    await client.post(f"/api/operator/rooms/{room.id}/stop", headers=headers)

    assert sent_feed_states(listener) == ["stopped"]
