from sqlalchemy import select

from app.models import Church, Room, User


async def seed_church(db_session, qr_hash: str, room_states: tuple[bool, ...] = ()):
    church = Church(name="Osaka Church", qr_code_hash=qr_hash)
    db_session.add(church)
    await db_session.commit()
    await db_session.refresh(church)

    rooms = []
    for is_live in room_states:
        room = Room(church_id=church.id, is_live=is_live)
        db_session.add(room)
        await db_session.commit()
        await db_session.refresh(room)
        rooms.append(room)

    return church, rooms


async def test_join_rejects_an_unknown_hash(client):
    response = await client.post("/api/join/not-a-real-hash")

    assert response.status_code == 404


async def test_join_a_live_church_returns_its_room(client, db_session):
    _, (room,) = await seed_church(db_session, "live-hash", room_states=(True,))

    response = await client.post("/api/join/live-hash")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["church_name"] == "Osaka Church"
    assert body["is_live"] is True
    assert body["room_id"] == room.id


async def test_join_before_the_feed_starts_returns_the_room_to_wait_in(
    client, db_session
):
    _, (room,) = await seed_church(db_session, "waiting-hash", room_states=(False,))

    response = await client.post("/api/join/waiting-hash")

    assert response.status_code == 200
    body = response.json()
    assert body["is_live"] is False
    assert body["room_id"] == room.id


async def test_join_prefers_the_live_room_when_a_church_has_several(
    client, db_session
):
    _, (_, live_room) = await seed_church(
        db_session, "two-rooms-hash", room_states=(False, True)
    )

    response = await client.post("/api/join/two-rooms-hash")

    body = response.json()
    assert body["is_live"] is True
    assert body["room_id"] == live_room.id


async def test_join_a_church_without_a_room_reports_no_room(client, db_session):
    await seed_church(db_session, "roomless-hash")

    response = await client.post("/api/join/roomless-hash")

    assert response.status_code == 200
    body = response.json()
    assert body["is_live"] is False
    assert body["room_id"] is None


async def test_join_registers_the_guest(client, db_session):
    await seed_church(db_session, "guest-hash")

    response = await client.post("/api/join/guest-hash")

    guest = (
        await db_session.execute(
            select(User).where(User.id == response.json()["user_id"])
        )
    ).scalar_one()
    assert guest.is_guest is True
