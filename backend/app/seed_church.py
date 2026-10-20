import argparse
import asyncio
import getpass
import os
import secrets
import sys
from dataclasses import dataclass
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import hash_password


class SeedChurchError(ValueError):
    pass


class PasswordRequiredError(SeedChurchError):
    pass


@dataclass(frozen=True)
class SeedChurchResult:
    church_id: int
    church_name: str
    room_id: int
    room_is_live: bool
    operator_email: str
    qr_code_hash: str
    church_created: bool
    room_created: bool
    operator_created: bool
    password_changed: bool


def _require_password(password: str | None) -> str:
    if not password:
        raise PasswordRequiredError(
            "A password is required for a new operator or a password reset."
        )
    return password


async def seed_church(
    session: AsyncSession,
    *,
    church_name: str,
    email: str,
    password: str | None = None,
    reset_password: bool = False,
) -> SeedChurchResult:
    from .models import Church, Room, User, new_qr_hash

    church_name = church_name.strip()
    email = email.strip()
    if not church_name:
        raise SeedChurchError("Church name is required.")
    if not email:
        raise SeedChurchError("Operator email is required.")

    try:
        operator = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if operator is not None and operator.is_guest:
            raise SeedChurchError(
                f"Operator email {email!r} belongs to a guest account."
            )

        churches = (
            (
                await session.execute(
                    select(Church).where(Church.name == church_name)
                )
            )
            .scalars()
            .all()
        )
        if len(churches) > 1:
            raise SeedChurchError(
                f"More than one church is named {church_name!r}. "
                "Rename or remove duplicates before onboarding."
            )

        church = churches[0] if churches else None
        if operator is not None and operator.church_id is not None:
            if church is None or church.id != operator.church_id:
                raise SeedChurchError(
                    f"Operator email {email!r} already belongs to another church."
                )

        needs_password = (
            operator is None
            or operator.hashed_password is None
            or reset_password
        )
        if needs_password:
            _require_password(password)

        church_created = church is None
        if church is None:
            church = Church(name=church_name, qr_code_hash=new_qr_hash())
            session.add(church)
            await session.flush()
        elif not church.qr_code_hash:
            church.qr_code_hash = new_qr_hash()

        room = (
            await session.execute(
                select(Room)
                .where(Room.church_id == church.id)
                .order_by(Room.id)
                .limit(1)
            )
        ).scalar_one_or_none()
        room_created = room is None
        if room is None:
            room = Room(church_id=church.id, is_live=False)
            session.add(room)
            await session.flush()

        operator_created = operator is None
        password_changed = False
        if operator is None:
            operator = User(
                email=email,
                hashed_password=hash_password(_require_password(password)),
                is_guest=False,
                church_id=church.id,
            )
            session.add(operator)
            password_changed = True
        else:
            operator.is_guest = False
            operator.church_id = church.id
            if reset_password or operator.hashed_password is None:
                operator.hashed_password = hash_password(_require_password(password))
                password_changed = True
        await session.flush()

        result = SeedChurchResult(
            church_id=church.id,
            church_name=church_name,
            room_id=room.id,
            room_is_live=bool(room.is_live),
            operator_email=email,
            qr_code_hash=church.qr_code_hash,
            church_created=church_created,
            room_created=room_created,
            operator_created=operator_created,
            password_changed=password_changed,
        )
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Onboard a church and its first operator in the Kizuna database."
    )
    parser.add_argument("--church-name", required=True)
    parser.add_argument("--email", required=True)
    password_group = parser.add_mutually_exclusive_group()
    password_group.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the operator password from the first line of stdin.",
    )
    password_group.add_argument(
        "--generate-password",
        action="store_true",
        help="Generate a strong password and print it once.",
    )
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Replace the existing operator password.",
    )
    parser.add_argument(
        "--public-origin",
        default=os.getenv("PUBLIC_ORIGIN"),
        help="Origin used in printed URLs (defaults to PUBLIC_ORIGIN).",
    )
    return parser


def _read_password(args: argparse.Namespace) -> tuple[str, str | None]:
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
        if not password:
            raise SeedChurchError("No password was received on stdin.")
        return password, None

    if args.generate_password:
        password = secrets.token_urlsafe(24)
        return password, password

    password = getpass.getpass("Operator password: ")
    if not password:
        raise SeedChurchError("Password cannot be empty.")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SeedChurchError("Passwords do not match.")
    return password, None


def _origin(value: str | None) -> str:
    origin = (value or "http://localhost:5173").rstrip("/")
    if not origin.startswith(("http://", "https://")):
        raise SeedChurchError(
            "Public origin must start with http:// or https://."
        )
    return origin


def _print_result(result: SeedChurchResult, public_origin: str | None) -> None:
    origin = _origin(public_origin)
    church_state = "created" if result.church_created else "existing"
    room_state = "created" if result.room_created else "existing"
    operator_state = "created" if result.operator_created else "existing"
    password_state = "changed" if result.password_changed else "unchanged"

    print(f"Church: {result.church_name} (id={result.church_id}, {church_state})")
    print(
        f"Room: id={result.room_id}, live={str(result.room_is_live).lower()} "
        f"({room_state})"
    )
    print(f"Operator: {result.operator_email} ({operator_state})")
    print(f"Password: {password_state}")
    print(f"QR hash: {result.qr_code_hash}")
    print(f"Guest join URL: {origin}/?qr={quote(result.qr_code_hash)}")
    print(f"Operator URL: {origin}/operate")
    if not public_origin:
        print(
            "Note: using the local development origin. "
            "Set PUBLIC_ORIGIN or pass --public-origin for production links."
        )


async def _run(args: argparse.Namespace) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from . import models

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(models.Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            generated_password = None
            try:
                result = await seed_church(
                    session,
                    church_name=args.church_name,
                    email=args.email,
                    password=None,
                    reset_password=args.reset_password,
                )
            except PasswordRequiredError:
                password, generated_password = _read_password(args)
                result = await seed_church(
                    session,
                    church_name=args.church_name,
                    email=args.email,
                    password=password,
                    reset_password=args.reset_password,
                )

            _print_result(result, args.public_origin)
            if generated_password is not None:
                print(f"Generated password (shown once): {generated_password}")
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    if not os.getenv("DATABASE_URL"):
        raise SystemExit(
            "DATABASE_URL is not set. Export it before running this command."
        )
    try:
        asyncio.run(_run(args))
    except SeedChurchError as exc:
        raise SystemExit(f"Onboarding failed: {exc}") from exc


if __name__ == "__main__":
    main()
