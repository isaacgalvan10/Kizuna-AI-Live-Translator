from sqlalchemy import text

from app.auth import hash_password
from app.models import Church, Room, User


async def test_operator_church_requires_token(client, operator_setup):
    response = await client.get("/api/operator/church")

    assert response.status_code == 401


async def test_operator_church_rejects_invalid_token(client, operator_setup):
    response = await client.get(
        "/api/operator/church", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401


async def test_operator_church_returns_name_rooms_and_qr_hash(
    client, db_session, operator_setup, auth_headers
):
    room = Room(church_id=operator_setup["church"].id, is_live=False)
    db_session.add(room)
    await db_session.commit()
    await db_session.refresh(room)

    headers = await auth_headers()
    response = await client.get("/api/operator/church", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "id": operator_setup["church"].id,
        "name": "Kizuna Test Church",
        "qr_code_hash": "test-hash-123",
        "rooms": [{"id": room.id, "is_live": False}],
    }


async def test_operator_church_generates_a_missing_qr_hash_once(
    client, db_session
):
    # A NULL hash can only exist in legacy rows: the ORM default fires even for
    # an explicit None, so seed via raw SQL to reach the backfill branch.
    await db_session.execute(
        text("INSERT INTO churches (name, qr_code_hash) VALUES ('Legacy Church', NULL)")
    )
    await db_session.commit()
    church_id = (
        await db_session.execute(
            text("SELECT id FROM churches WHERE name = 'Legacy Church'")
        )
    ).scalar_one()
    operator = User(
        email="new-operator@test.church",
        hashed_password=hash_password("new-operator-password"),
        is_guest=False,
        church_id=church_id,
    )
    db_session.add(operator)
    await db_session.commit()

    login = await client.post(
        "/api/operator/login",
        json={"email": operator.email, "password": "new-operator-password"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    first = await client.get("/api/operator/church", headers=headers)
    second = await client.get("/api/operator/church", headers=headers)

    first_hash = first.json()["qr_code_hash"]
    assert first_hash
    assert second.json()["qr_code_hash"] == first_hash
    stored = (
        await db_session.execute(
            text("SELECT qr_code_hash FROM churches WHERE id = :id"),
            {"id": church_id},
        )
    ).scalar_one()
    assert stored == first_hash


async def test_operator_church_lists_only_its_own_rooms(
    client, db_session, operator_setup, auth_headers
):
    own_room = Room(church_id=operator_setup["church"].id, is_live=True)
    other_church = Church(name="Second Church", qr_code_hash="second-hash-456")
    db_session.add_all([own_room, other_church])
    await db_session.commit()
    await db_session.refresh(own_room)
    await db_session.refresh(other_church)
    other_room = Room(church_id=other_church.id, is_live=True)
    db_session.add(other_room)
    await db_session.commit()
    await db_session.refresh(other_room)

    headers = await auth_headers()
    response = await client.get("/api/operator/church", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == operator_setup["church"].id
    assert [room["id"] for room in body["rooms"]] == [own_room.id]


async def test_operator_church_reports_live_state(
    client, db_session, operator_setup, auth_headers
):
    live_room = Room(church_id=operator_setup["church"].id, is_live=True)
    db_session.add(live_room)
    await db_session.commit()
    await db_session.refresh(live_room)

    headers = await auth_headers()
    response = await client.get("/api/operator/church", headers=headers)

    assert response.status_code == 200
    assert response.json()["rooms"] == [{"id": live_room.id, "is_live": True}]
