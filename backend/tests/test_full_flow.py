"""End-to-end Sunday flow tests: operator console -> guest listener.

These tests drive the real HTTP and WebSocket endpoints through starlette's
TestClient. The one stand-in is the Gemini worker, an external service: it is
swapped for a fake that turns received audio into a canned translation pair,
so the tests exercise the full operator -> manager -> listener path without
calling the Gemini API. As in test_stream_auth, the app runs on TestClient's
own event loop, so the database is a temp *file* SQLite database.
"""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.main as main_module
from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import Church, Room, User
from app.socket_manager import manager

FIRST_PASSWORD = "first-church-password"
SECOND_PASSWORD = "second-church-password"
FIRST_HASH = "first-church-hash"
SECOND_HASH = "second-church-hash"
FIRST_EMAIL = "operator@first.church"
SECOND_EMAIL = "operator@second.church"

CANNED_TRANSCRIPT = "神の言葉は生きています。"
CANNED_TRANSLATIONS = {
    "en": "The word of God is living.",
    "ko": "하나님의 말씀은 살아 있습니다.",
    "zh-hans": "神的道是活泼的。",
}


class FakeGeminiWorker:
    """Stands in for the Gemini-backed worker so no API call leaves the test."""

    def __init__(
        self,
        room_id: str,
        loop: asyncio.AbstractEventLoop,
        *,
        glossary=None,
    ):
        self.room_id = room_id
        self.glossary = glossary

    def start(self):
        pass

    def stop(self):
        pass

    def process_audio_chunk(self, chunk: bytes):
        for code in manager.get_active_languages(self.room_id):
            translation = CANNED_TRANSLATIONS.get(code)
            if translation is None:
                continue
            asyncio.get_running_loop().create_task(
                manager.broadcast_to_language(
                    CANNED_TRANSCRIPT, translation, self.room_id, code
                )
            )


def seed_churches(db_path: Path) -> dict:
    ids: dict = {}

    async def _seed():
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            first = Church(name="First Church", qr_code_hash=FIRST_HASH)
            second = Church(name="Second Church", qr_code_hash=SECOND_HASH)
            session.add_all([first, second])
            await session.commit()
            await session.refresh(first)
            await session.refresh(second)

            first_room = Room(church_id=first.id, is_live=False)
            second_room = Room(church_id=second.id, is_live=False)
            session.add_all([first_room, second_room])
            session.add_all(
                [
                    User(
                        email=FIRST_EMAIL,
                        hashed_password=hash_password(FIRST_PASSWORD),
                        is_guest=False,
                        church_id=first.id,
                    ),
                    User(
                        email=SECOND_EMAIL,
                        hashed_password=hash_password(SECOND_PASSWORD),
                        is_guest=False,
                        church_id=second.id,
                    ),
                ]
            )
            await session.commit()
            await session.refresh(first_room)
            await session.refresh(second_room)

            ids.update(
                first_room=first_room.id,
                second_room=second_room.id,
            )

        await engine.dispose()

    asyncio.run(_seed())
    return ids


@pytest.fixture
def flow_db(tmp_path, monkeypatch, file_db_override):
    db_path = tmp_path / "flow.db"
    ids = seed_churches(db_path)
    app.dependency_overrides[get_db] = file_db_override(db_path)
    monkeypatch.setattr(main_module, "GeminiWorker", FakeGeminiWorker)
    manager.active_connections.clear()
    manager.history_buffer.clear()
    yield ids
    app.dependency_overrides.clear()
    manager.active_connections.clear()
    manager.history_buffer.clear()


def operator_token(client: TestClient, email: str, password: str) -> str:
    login = client.post("/api/operator/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_guest_who_scans_before_start_waits_and_then_follows_the_feed(flow_db):
    with TestClient(app) as client:
        token = operator_token(client, FIRST_EMAIL, FIRST_PASSWORD)
        room = flow_db["first_room"]

        # The QR scan happens before the operator starts: the guest still gets
        # a room to wait in, so the scan never needs to be repeated.
        join = client.post(f"/api/join/{FIRST_HASH}")
        assert join.status_code == 200
        assert join.json()["is_live"] is False
        assert join.json()["room_id"] == room

        with client.websocket_connect(f"/ws/listen/{room}/en") as listener:
            with client.websocket_connect(f"/ws/stream/{room}?token={token}") as stream:
                start = client.post(f"/api/operator/rooms/{room}/start", headers=auth(token))
                assert start.json() == {"status": "live"}
                assert listener.receive_json() == {"type": "feed_state", "data": "live"}

                # The operator's mixer audio flows through the worker and comes
                # back out to the guest as a transcript + translation pair.
                stream.send_bytes(b"\x00\x01" * 480)
                assert listener.receive_json() == {
                    "type": "live_translation",
                    "data": {
                        "original": CANNED_TRANSCRIPT,
                        "translation": CANNED_TRANSLATIONS["en"],
                    },
                }


def test_pause_resume_and_stop_reach_the_guest(flow_db):
    with TestClient(app) as client:
        token = operator_token(client, FIRST_EMAIL, FIRST_PASSWORD)
        room = flow_db["first_room"]

        with client.websocket_connect(f"/ws/listen/{room}/en") as listener:
            with client.websocket_connect(f"/ws/stream/{room}?token={token}") as stream:
                start = client.post(f"/api/operator/rooms/{room}/start", headers=auth(token))
                assert start.json() == {"status": "live"}
                assert listener.receive_json() == {"type": "feed_state", "data": "live"}

                pause = client.post(f"/api/operator/rooms/{room}/pause", headers=auth(token))
                assert pause.json() == {"status": "paused"}
                assert listener.receive_json() == {"type": "feed_state", "data": "paused"}

                resume = client.post(f"/api/operator/rooms/{room}/start", headers=auth(token))
                assert resume.json() == {"status": "live"}
                assert listener.receive_json() == {"type": "feed_state", "data": "live"}

                # After the resume the guest receives translations again.
                stream.send_bytes(b"\x00\x01" * 480)
                assert listener.receive_json() == {
                    "type": "live_translation",
                    "data": {
                        "original": CANNED_TRANSCRIPT,
                        "translation": CANNED_TRANSLATIONS["en"],
                    },
                }

                stop = client.post(f"/api/operator/rooms/{room}/stop", headers=auth(token))
                assert stop.json() == {"status": "stopped"}
                assert listener.receive_json() == {"type": "feed_state", "data": "stopped"}


def test_a_second_church_never_sees_or_controls_the_first_churchs_feed(flow_db):
    with TestClient(app) as client:
        first_token = operator_token(client, FIRST_EMAIL, FIRST_PASSWORD)
        second_token = operator_token(client, SECOND_EMAIL, SECOND_PASSWORD)
        first_room = flow_db["first_room"]
        second_room = flow_db["second_room"]

        # The second church's QR resolves only to its own room.
        join = client.post(f"/api/join/{SECOND_HASH}")
        assert join.json()["room_id"] == second_room

        # Its operator cannot touch the first church's room.
        for action in ("start", "pause", "stop"):
            response = client.post(
                f"/api/operator/rooms/{first_room}/{action}", headers=auth(second_token)
            )
            assert response.status_code == 404

        with client.websocket_connect(f"/ws/listen/{first_room}/en") as first_listener:
            with client.websocket_connect(f"/ws/listen/{second_room}/ko") as second_listener:
                with client.websocket_connect(
                    f"/ws/stream/{second_room}?token={second_token}"
                ) as second_stream:
                    client.post(
                        f"/api/operator/rooms/{second_room}/start", headers=auth(second_token)
                    )
                    second_stream.send_bytes(b"\x00\x01" * 480)

                    assert second_listener.receive_json() == {
                        "type": "feed_state",
                        "data": "live",
                    }
                    assert second_listener.receive_json() == {
                        "type": "live_translation",
                        "data": {
                            "original": CANNED_TRANSCRIPT,
                            "translation": CANNED_TRANSLATIONS["ko"],
                        },
                    }

                # The first church starts and streams its own feed. Its
                # listener's very first message must be its own live event: had
                # the second church's translation leaked across rooms, it would
                # arrive here first and this assertion would catch it.
                client.post(f"/api/operator/rooms/{first_room}/start", headers=auth(first_token))
                with client.websocket_connect(
                    f"/ws/stream/{first_room}?token={first_token}"
                ) as first_stream:
                    assert first_listener.receive_json() == {
                        "type": "feed_state",
                        "data": "live",
                    }
                    first_stream.send_bytes(b"\x00\x01" * 480)
                    assert first_listener.receive_json() == {
                        "type": "live_translation",
                        "data": {
                            "original": CANNED_TRANSCRIPT,
                            "translation": CANNED_TRANSLATIONS["en"],
                        },
                    }

                # And the same guarantee in the other direction: the second
                # church stops, and its listener's next message is its own stop
                # event, not the first church's translation.
                client.post(f"/api/operator/rooms/{second_room}/stop", headers=auth(second_token))
                assert second_listener.receive_json() == {"type": "feed_state", "data": "stopped"}
