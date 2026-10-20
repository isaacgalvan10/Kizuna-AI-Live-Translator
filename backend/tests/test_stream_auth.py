"""Handshake-level tests for the operator audio stream WebSocket.

These tests use starlette's TestClient so the WebSocket handshake is exercised
end to end. Because TestClient runs the app on its own event loop, the database
is a temp *file* SQLite database: the test seeds it on a throwaway loop, and the
dependency override opens a fresh engine inside the app's loop.
"""

import asyncio
import json
import logging
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.testclient import WebSocketDisconnect

import app.main as main_module
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
    ids["db_path"] = db_path
    app.dependency_overrides[get_db] = file_db_override(db_path)
    yield ids
    app.dependency_overrides.clear()


def store_glossary(db_path: Path, church_id: int, content: str) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO church_glossaries (church_id, content) "
            "VALUES (?, ?)",
            (church_id, content),
        )
        connection.commit()


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


def test_stream_handshake_passes_the_church_glossary_to_the_worker(
    stream_db,
    monkeypatch,
):
    captured = {}

    class CapturingWorker:
        def __init__(self, room_id, loop, *, glossary=None):
            captured["room_id"] = room_id
            captured["glossary"] = glossary

        def start(self):
            pass

        def stop(self):
            pass

        def process_audio_chunk(self, chunk):
            pass

    monkeypatch.setattr(main_module, "GeminiWorker", CapturingWorker)
    store_glossary(
        stream_db["db_path"],
        stream_db["first"]["church"],
        json.dumps(
            {"names": [{"japanese": "山田牧師", "en": "Pastor Yamada"}]},
            ensure_ascii=False,
        ),
    )
    token = create_operator_token(
        "operator@first.church",
        stream_db["first"]["church"],
    )

    with TestClient(app) as client:
        with client.websocket_connect(
            f"/ws/stream/{stream_db['first']['room']}?token={token}"
        ):
            pass

    glossary = captured["glossary"]
    assert glossary is not None
    assert glossary.names[0].japanese == "山田牧師"
    assert glossary.names[0].translations == {"en": "Pastor Yamada"}


def test_stream_handshake_rejects_an_invalid_church_glossary(
    stream_db,
    caplog,
):
    caplog.set_level(logging.ERROR, logger="app.main")
    store_glossary(
        stream_db["db_path"],
        stream_db["first"]["church"],
        json.dumps(
            {
                "names": [
                    {"japanese": "山田牧師", "en": "Pastor Yamada"},
                    {"japanese": "山田牧師", "en": "Pastor Yamada"},
                ]
            },
            ensure_ascii=False,
        ),
    )
    token = create_operator_token(
        "operator@first.church",
        stream_db["first"]["church"],
    )

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                f"/ws/stream/{stream_db['first']['room']}?token={token}"
            ):
                pass

    assert exc.value.code == 1011
    assert "church_glossary_invalid" in caplog.text
    assert "山田牧師" not in caplog.text
    assert "Duplicate" not in caplog.text
