import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-kizuna")

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import Church, User

TEST_PASSWORD = "gracious-and-true"


@pytest.fixture
def file_db_override():
    """Builds a get_db override backed by a temp *file* SQLite database.

    TestClient runs the app on its own event loop, so WebSocket tests cannot
    reuse the in-memory engine the other fixtures provide: the engine must be
    created lazily inside a session that the app's loop owns.
    """

    def build(db_path: Path):
        holder: dict = {}

        async def override():
            engine = holder.get("engine")
            if engine is None:
                engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
                holder["engine"] = engine
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                yield session

        return override

    return build


@pytest.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client
    app.dependency_overrides.clear()


@pytest.fixture
async def operator_setup(db_session):
    church = Church(name="Kizuna Test Church", qr_code_hash="test-hash-123")
    db_session.add(church)
    await db_session.commit()
    await db_session.refresh(church)

    operator = User(
        email="operator@test.church",
        hashed_password=hash_password(TEST_PASSWORD),
        is_guest=False,
        church_id=church.id,
    )
    guest = User(
        email="guest@test.church",
        hashed_password=hash_password(TEST_PASSWORD),
        is_guest=True,
        church_id=church.id,
    )
    db_session.add_all([operator, guest])
    await db_session.commit()
    await db_session.refresh(operator)
    await db_session.refresh(guest)

    return {"church": church, "operator": operator, "guest": guest, "password": TEST_PASSWORD}


@pytest.fixture
async def auth_headers(client, operator_setup):
    async def _auth_headers():
        response = await client.post(
            "/api/operator/login",
            json={
                "email": operator_setup["operator"].email,
                "password": operator_setup["password"],
            },
        )
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _auth_headers
