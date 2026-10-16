from app.models import Church, Room


async def test_operator_church_requires_token(client, operator_setup):
    response = await client.get("/api/operator/church")

    assert response.status_code == 401


async def test_operator_church_rejects_invalid_token(client, operator_setup):
    response = await client.get(
        "/api/operator/church", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401


async def test_operator_church_returns_name_and_rooms(
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
        "rooms": [{"id": room.id, "is_live": False}],
    }


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
