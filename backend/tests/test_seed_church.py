import argparse
import io
import re
import sqlite3

import pytest
from sqlalchemy import func, select, text

from app.auth import verify_password
from app.models import Church, Room, User
from app.seed_church import (
    PasswordRequiredError,
    SeedChurchError,
    _origin,
    _read_password,
    main,
    seed_church,
)


async def _count(session, model) -> int:
    return (
        await session.execute(select(func.count()).select_from(model))
    ).scalar_one()


async def test_seed_church_creates_church_room_and_operator(db_session):
    result = await seed_church(
        db_session,
        church_name="Grace Church",
        email="operator@grace.test",
        password="initial-password",
    )

    assert result.church_created is True
    assert result.room_created is True
    assert result.operator_created is True
    assert result.password_changed is True
    assert result.room_is_live is False
    assert result.qr_code_hash

    church = (await db_session.execute(select(Church))).scalar_one()
    room = (await db_session.execute(select(Room))).scalar_one()
    operator = (await db_session.execute(select(User))).scalar_one()

    assert church.id == result.church_id
    assert church.name == "Grace Church"
    assert church.qr_code_hash == result.qr_code_hash
    assert room.id == result.room_id
    assert room.church_id == church.id
    assert room.is_live is False
    assert operator.email == "operator@grace.test"
    assert operator.church_id == church.id
    assert operator.is_guest is False
    assert verify_password("initial-password", operator.hashed_password)


async def test_seed_church_rerun_is_idempotent_and_keeps_password(db_session):
    first = await seed_church(
        db_session,
        church_name="Grace Church",
        email="operator@grace.test",
        password="initial-password",
    )
    second = await seed_church(
        db_session,
        church_name="Grace Church",
        email="operator@grace.test",
        password="ignored-password",
    )

    assert second.church_created is False
    assert second.room_created is False
    assert second.operator_created is False
    assert second.password_changed is False
    assert second.church_id == first.church_id
    assert second.room_id == first.room_id
    assert second.qr_code_hash == first.qr_code_hash
    assert await _count(db_session, Church) == 1
    assert await _count(db_session, Room) == 1
    assert await _count(db_session, User) == 1

    operator = (await db_session.execute(select(User))).scalar_one()
    assert verify_password("initial-password", operator.hashed_password)
    assert not verify_password("ignored-password", operator.hashed_password)


async def test_seed_church_rerun_without_a_password_keeps_the_existing_password(
    db_session,
):
    await seed_church(
        db_session,
        church_name="Grace Church",
        email="operator@grace.test",
        password="initial-password",
    )
    result = await seed_church(
        db_session,
        church_name="Grace Church",
        email="operator@grace.test",
    )

    assert result.password_changed is False
    operator = (await db_session.execute(select(User))).scalar_one()
    assert verify_password("initial-password", operator.hashed_password)


async def test_seed_church_adds_a_second_operator_to_the_same_church(db_session):
    first = await seed_church(
        db_session,
        church_name="Grace Church",
        email="first@grace.test",
        password="first-password",
    )
    second = await seed_church(
        db_session,
        church_name="Grace Church",
        email="second@grace.test",
        password="second-password",
    )

    assert second.church_created is False
    assert second.room_created is False
    assert second.operator_created is True
    assert second.church_id == first.church_id
    assert second.room_id == first.room_id
    assert await _count(db_session, Church) == 1
    assert await _count(db_session, Room) == 1
    assert await _count(db_session, User) == 2

    operators = (
        (await db_session.execute(select(User).order_by(User.email)))
        .scalars()
        .all()
    )
    assert [operator.email for operator in operators] == [
        "first@grace.test",
        "second@grace.test",
    ]
    assert all(
        operator.church_id == first.church_id and not operator.is_guest
        for operator in operators
    )


async def test_seed_church_rejects_an_email_from_another_church(db_session):
    first = await seed_church(
        db_session,
        church_name="Grace Church",
        email="shared@example.com",
        password="initial-password",
    )

    with pytest.raises(SeedChurchError, match="another church"):
        await seed_church(
            db_session,
            church_name="Other Church",
            email="shared@example.com",
            password="other-password",
        )

    assert await _count(db_session, Church) == 1
    assert await _count(db_session, Room) == 1
    assert await _count(db_session, User) == 1
    church = (await db_session.execute(select(Church))).scalar_one()
    assert church.id == first.church_id


async def test_seed_church_rejects_a_guest_email(db_session):
    church = Church(name="Existing Church", qr_code_hash="existing-hash")
    db_session.add(church)
    await db_session.commit()
    await db_session.refresh(church)

    guest = User(email="guest@example.com", is_guest=True, church_id=church.id)
    db_session.add(guest)
    await db_session.commit()

    with pytest.raises(SeedChurchError, match="guest account"):
        await seed_church(
            db_session,
            church_name="New Church",
            email="guest@example.com",
            password="new-password",
        )

    assert await _count(db_session, Church) == 1
    assert await _count(db_session, Room) == 0
    assert await _count(db_session, User) == 1


async def test_seed_church_requires_a_password_for_a_new_operator(db_session):
    with pytest.raises(PasswordRequiredError):
        await seed_church(
            db_session,
            church_name="Grace Church",
            email="operator@grace.test",
        )

    assert await _count(db_session, Church) == 0
    assert await _count(db_session, Room) == 0
    assert await _count(db_session, User) == 0


async def test_seed_church_resets_the_password(db_session):
    await seed_church(
        db_session,
        church_name="Grace Church",
        email="operator@grace.test",
        password="old-password",
    )
    result = await seed_church(
        db_session,
        church_name="Grace Church",
        email="operator@grace.test",
        password="new-password",
        reset_password=True,
    )

    assert result.operator_created is False
    assert result.password_changed is True
    operator = (await db_session.execute(select(User))).scalar_one()
    assert verify_password("new-password", operator.hashed_password)
    assert not verify_password("old-password", operator.hashed_password)


async def test_seed_church_rejects_an_ambiguous_church_name(db_session):
    db_session.add_all(
        [
            Church(name="Same Name", qr_code_hash="hash-one"),
            Church(name="Same Name", qr_code_hash="hash-two"),
        ]
    )
    await db_session.commit()

    with pytest.raises(SeedChurchError, match="More than one church"):
        await seed_church(
            db_session,
            church_name="Same Name",
            email="operator@example.com",
            password="initial-password",
        )

    assert await _count(db_session, Room) == 0
    assert await _count(db_session, User) == 0


async def test_seed_church_backfills_a_missing_qr_hash(db_session):
    await db_session.execute(
        text(
            "INSERT INTO churches (name, qr_code_hash) "
            "VALUES ('Legacy Church', NULL)"
        )
    )
    await db_session.commit()

    first = await seed_church(
        db_session,
        church_name="Legacy Church",
        email="operator@legacy.test",
        password="initial-password",
    )
    second = await seed_church(
        db_session,
        church_name="Legacy Church",
        email="operator@legacy.test",
    )

    assert first.church_created is False
    assert first.qr_code_hash
    assert second.qr_code_hash == first.qr_code_hash


def test_read_password_reads_stdin(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("secret-password\n"))
    args = argparse.Namespace(password_stdin=True, generate_password=False)

    password, generated = _read_password(args)

    assert password == "secret-password"
    assert generated is None


def test_read_password_generates_a_password():
    args = argparse.Namespace(password_stdin=False, generate_password=True)

    password, generated = _read_password(args)

    assert password == generated
    assert len(password) >= 24


def test_read_password_rejects_mismatched_interactive_input(monkeypatch):
    responses = iter(["first-password", "second-password"])
    monkeypatch.setattr(
        "app.seed_church.getpass.getpass",
        lambda prompt="": next(responses),
    )
    args = argparse.Namespace(password_stdin=False, generate_password=False)

    with pytest.raises(SeedChurchError, match="do not match"):
        _read_password(args)


def test_origin_rejects_a_non_http_url():
    with pytest.raises(SeedChurchError, match="http"):
        _origin("church.example")


def test_main_reads_password_from_stdin_and_prints_urls(
    tmp_path,
    monkeypatch,
    capsys,
):
    db_path = tmp_path / "cli.db"
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
    )
    monkeypatch.setattr("sys.stdin", io.StringIO("cli-password\n"))

    main(
        [
            "--church-name",
            "CLI Church",
            "--email",
            "cli@example.com",
            "--password-stdin",
            "--public-origin",
            "https://church.example",
        ]
    )

    output = capsys.readouterr().out
    assert "Church: CLI Church" in output
    assert "Guest join URL: https://church.example/?qr=" in output
    assert "Operator URL: https://church.example/operate" in output
    assert "cli-password" not in output

    with sqlite3.connect(db_path) as connection:
        email, hashed_password = connection.execute(
            "SELECT email, hashed_password FROM users"
        ).fetchone()
    assert email == "cli@example.com"
    assert verify_password("cli-password", hashed_password)


def test_main_generates_and_prints_a_password_once(
    tmp_path,
    monkeypatch,
    capsys,
):
    db_path = tmp_path / "generated.db"
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
    )

    main(
        [
            "--church-name",
            "Generated Church",
            "--email",
            "generated@example.com",
            "--generate-password",
        ]
    )

    output = capsys.readouterr().out
    match = re.search(r"Generated password \(shown once\): (\S+)", output)
    assert match is not None
    password = match.group(1)
    assert output.count(password) == 1

    with sqlite3.connect(db_path) as connection:
        hashed_password = connection.execute(
            "SELECT hashed_password FROM users WHERE email = ?",
            ("generated@example.com",),
        ).fetchone()[0]
    assert verify_password(password, hashed_password)


def test_main_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(SystemExit, match="DATABASE_URL"):
        main(
            [
                "--church-name",
                "No Database",
                "--email",
                "no-db@example.com",
            ]
        )
