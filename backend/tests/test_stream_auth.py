"""Handshake-level tests for the operator audio stream WebSocket.

These tests use starlette's TestClient so the WebSocket handshake is exercised
end to end. Because TestClient runs the app on its own event loop, the database
is a temp *file* SQLite database: the test seeds it on a throwaway loop, and the
dependency override opens a fresh engine inside the app's loop.
"""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.testclient import WebSocketDisconnect

from app.auth import create_operator_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models import Church, Room, User


def seed_file_database(db_path: Path) -> dict:
    first_ids = {}
    second_ids = {}

    async def _seed():
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            first = Church(name="First Church", qr_code_hash="first-hash")
            second = Church(name="Second Church", qr_code_hash="second-hash")
            session.add_all([first, second])
            await session.commit()
            await session.refresh(first)
            await session.refresh(second)

            first_room = Room(church_id=first.id, is_live=False)
            second_room = Room(church_id=second.id, is_live=False)
            session.add_all([first_room, second_room])
            session.add(
                User(
                    email="operator@first.church",
                    hashed_password=hash_password("first-password"),
                    is_guest=False,
                    church_id=first.id,
                )
            )
            await session.commit()
            await session.refresh(first_room)
            await session.refresh(second_room)

            first_ids.update(church=first.id, room=first_room.id)
            second_ids.update(church=second.id, room=second_room.id)

        await engine.dispose()

    asyncio.run(_seed())
    return {"first": first_ids, "second": second_ids}


@pytest.fixture
def stream_db(tmp_path, file_db_override):
    db_path = tmp_path / "stream.db"
    ids = seed_file_database(db_path)
    app.dependency_overrides[get_db] = file_db_override(db_path)
    yield ids
    app.dependency_overrides.clear()


def test_stream_handshake_without_token_is_rejected(stream_db):
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(f"/ws/stream/{stream_db['first']['room']}"):
                pass

    assert exc.value.code == 1008


def test_stream_handshake_with_garbage_token_is_rejected(stream_db):
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                f"/ws/stream/{stream_db['first']['room']}?token=not-a-real-token"
            ):
                pass

    assert exc.value.code == 1008


def test_stream_handshake_cannot_control_another_churchs_room(stream_db):
    token = create_operator_token("operator@first.church", stream_db["first"]["church"])

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                f"/ws/stream/{stream_db['second']['room']}?token={token}"
            ):
                pass

    assert exc.value.code == 1008


def test_stream_handshake_accepts_operator_for_own_room(stream_db):
    token = create_operator_token("operator@first.church", stream_db["first"]["church"])

    with TestClient(app) as client:
        with client.websocket_connect(
            f"/ws/stream/{stream_db['first']['room']}?token={token}"
        ) as websocket:
            websocket.send_bytes(b"\x00\x00" * 64)
