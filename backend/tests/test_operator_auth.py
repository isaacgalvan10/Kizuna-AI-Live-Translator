from datetime import datetime, timedelta, timezone

from jose import jwt

from app.auth import ALGORITHM, SECRET_KEY, hash_password
from app.models import User


async def test_valid_operator_login_returns_token_scoped_to_church(client, operator_setup):
    response = await client.post(
        "/api/operator/login",
        json={"email": operator_setup["operator"].email, "password": operator_setup["password"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["church_id"] == operator_setup["church"].id

    claims = jwt.decode(body["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
    assert claims["church_id"] == operator_setup["church"].id
    assert claims["sub"] == operator_setup["operator"].email
    assert "exp" in claims


async def test_login_rejects_wrong_password(client, operator_setup):
    response = await client.post(
        "/api/operator/login",
        json={"email": operator_setup["operator"].email, "password": "not-the-password"},
    )

    assert response.status_code == 401


async def test_login_rejects_unknown_email(client, operator_setup):
    response = await client.post(
        "/api/operator/login",
        json={"email": "nobody@test.church", "password": operator_setup["password"]},
    )

    assert response.status_code == 401


async def test_login_rejects_guest_users_even_with_credentials(client, operator_setup):
    response = await client.post(
        "/api/operator/login",
        json={"email": operator_setup["guest"].email, "password": operator_setup["password"]},
    )

    assert response.status_code == 401


async def test_login_rejects_operator_without_church(db_session, client, operator_setup):
    wanderer = User(
        email="wanderer@test.church",
        hashed_password=hash_password(operator_setup["password"]),
        is_guest=False,
        church_id=None,
    )
    db_session.add(wanderer)
    await db_session.commit()

    response = await client.post(
        "/api/operator/login",
        json={"email": wanderer.email, "password": operator_setup["password"]},
    )

    assert response.status_code == 401


async def test_login_rejects_corrupt_stored_hash(db_session, client, operator_setup):
    corrupt = User(
        email="corrupt@test.church",
        hashed_password="not-a-bcrypt-hash",
        is_guest=False,
        church_id=operator_setup["church"].id,
    )
    db_session.add(corrupt)
    await db_session.commit()

    response = await client.post(
        "/api/operator/login",
        json={"email": corrupt.email, "password": operator_setup["password"]},
    )

    assert response.status_code == 401


async def login_as_operator(client, operator_setup):
    response = await client.post(
        "/api/operator/login",
        json={"email": operator_setup["operator"].email, "password": operator_setup["password"]},
    )
    return response.json()["access_token"]


async def test_operator_profile_requires_token(client, operator_setup):
    response = await client.get("/api/operator/me")

    assert response.status_code == 401


async def test_operator_profile_rejects_invalid_token(client, operator_setup):
    response = await client.get(
        "/api/operator/me", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401


async def test_operator_profile_rejects_token_without_church_claim(client):
    orphan_token = jwt.encode({"sub": "orphan@test.church"}, SECRET_KEY, algorithm=ALGORITHM)

    response = await client.get(
        "/api/operator/me", headers={"Authorization": f"Bearer {orphan_token}"}
    )

    assert response.status_code == 401


async def test_operator_profile_rejects_expired_token(client, operator_setup):
    expired = jwt.encode(
        {
            "sub": operator_setup["operator"].email,
            "church_id": operator_setup["church"].id,
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    response = await client.get(
        "/api/operator/me", headers={"Authorization": f"Bearer {expired}"}
    )

    assert response.status_code == 401


async def test_operator_profile_returns_church_for_valid_token(client, operator_setup):
    token = await login_as_operator(client, operator_setup)

    response = await client.get(
        "/api/operator/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "email": operator_setup["operator"].email,
        "church_id": operator_setup["church"].id,
    }


async def test_dev_seed_creates_operator_that_can_log_in(client):
    seed = await client.post("/api/dev/seed")
    assert seed.status_code == 200
    body = seed.json()

    login = await client.post(
        "/api/operator/login",
        json={"email": body["operator_email"], "password": body["operator_password"]},
    )

    assert login.status_code == 200
    assert login.json()["church_id"] == body["church_id"]


async def test_dev_seed_is_idempotent(client):
    first = await client.post("/api/dev/seed")
    second = await client.post("/api/dev/seed")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["church_id"] == first.json()["church_id"]
