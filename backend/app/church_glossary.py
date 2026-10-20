import argparse
import asyncio
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .translation_prompt import SUPPORTED_LANGUAGES

GLOSSARY_FIELDS = frozenset({"names", "terms", "style", "scripture"})
SCRIPTURE_FIELDS = frozenset({"source", *SUPPORTED_LANGUAGES})
MAX_ENTRIES_PER_SECTION = 100
MAX_JAPANESE_LENGTH = 100
MAX_TRANSLATION_LENGTH = 200
MAX_STYLE_LENGTH = 500
MAX_SCRIPTURE_LENGTH = 100


class ChurchGlossaryError(ValueError):
    """Raised when a Church Glossary cannot be safely loaded."""


@dataclass(frozen=True)
class ChurchGlossaryEntry:
    japanese: str
    translations: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ChurchGlossary:
    names: tuple[ChurchGlossaryEntry, ...] = ()
    terms: tuple[ChurchGlossaryEntry, ...] = ()
    style: dict[str, str] = field(default_factory=dict)
    scripture: dict[str, str] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not (self.names or self.terms or self.style or self.scripture)


def _clean(value: str) -> str:
    return " ".join(value.split())


def _require_mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ChurchGlossaryError(f"{path} must be an object.")
    return value


def _require_text(value: object, path: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise ChurchGlossaryError(f"{path} must be a string.")
    cleaned = _clean(value)
    if not cleaned:
        raise ChurchGlossaryError(f"{path} must be a non-empty string.")
    if len(cleaned) > max_length:
        raise ChurchGlossaryError(
            f"{path} must be {max_length} characters or fewer."
        )
    return cleaned


def _parse_entries(
    value: object,
    section: str,
) -> tuple[ChurchGlossaryEntry, ...]:
    if not isinstance(value, list):
        raise ChurchGlossaryError(f"'{section}' must be a list of entries.")
    if len(value) > MAX_ENTRIES_PER_SECTION:
        raise ChurchGlossaryError(
            f"'{section}' must contain at most "
            f"{MAX_ENTRIES_PER_SECTION} entries."
        )

    entries: list[ChurchGlossaryEntry] = []
    for index, raw_entry in enumerate(value):
        path = f"{section}[{index}]"
        entry = _require_mapping(raw_entry, path)

        if "japanese" not in entry:
            raise ChurchGlossaryError(f"{path}.japanese is required.")
        japanese = _require_text(
            entry["japanese"],
            f"{path}.japanese",
            MAX_JAPANESE_LENGTH,
        )

        translations: dict[str, str] = {}
        for key, raw_translation in entry.items():
            if key == "japanese":
                continue
            if key not in SUPPORTED_LANGUAGES:
                raise ChurchGlossaryError(
                    f"{path} key '{key}' is not supported. "
                    f"Use one of: {', '.join(SUPPORTED_LANGUAGES)}."
                )
            translations[key] = _require_text(
                raw_translation,
                f"{path}.{key}",
                MAX_TRANSLATION_LENGTH,
            )

        if not translations:
            raise ChurchGlossaryError(
                f"{path} must include at least one translation for: "
                f"{', '.join(SUPPORTED_LANGUAGES)}."
            )
        entries.append(
            ChurchGlossaryEntry(
                japanese=japanese,
                translations=translations,
            )
        )
    return tuple(entries)


def _parse_language_text_map(
    value: object,
    field_name: str,
    *,
    allowed_fields: frozenset[str],
    max_length: int,
) -> dict[str, str]:
    mapping = _require_mapping(value, f"'{field_name}'")
    parsed: dict[str, str] = {}
    for key, raw_value in mapping.items():
        if key not in allowed_fields:
            if field_name == "scripture":
                raise ChurchGlossaryError(
                    f"Unknown Scripture field '{key}'."
                )
            raise ChurchGlossaryError(
                f"{field_name} key '{key}' is not supported. "
                f"Use one of: {', '.join(SUPPORTED_LANGUAGES)}."
            )
        parsed[key] = _require_text(
            raw_value,
            f"{field_name}.{key}",
            max_length,
        )
    return parsed


def _check_duplicate_entries(
    sections: tuple[tuple[str, tuple[ChurchGlossaryEntry, ...]], ...],
) -> None:
    section_by_term: dict[str, str] = {}
    for section, entries in sections:
        for entry in entries:
            previous = section_by_term.get(entry.japanese)
            if previous is not None:
                raise ChurchGlossaryError(
                    f"Duplicate glossary entry '{entry.japanese}' "
                    f"in {previous} and {section}."
                )
            section_by_term[entry.japanese] = section


def _parse_document(document: Mapping[str, object]) -> ChurchGlossary:
    unknown = set(document) - GLOSSARY_FIELDS
    if unknown:
        field_name = sorted(unknown)[0]
        raise ChurchGlossaryError(
            f"Unknown glossary field '{field_name}'. "
            f"Allowed fields: {', '.join(sorted(GLOSSARY_FIELDS))}."
        )

    names = _parse_entries(document.get("names", []), "names")
    terms = _parse_entries(document.get("terms", []), "terms")
    style = _parse_language_text_map(
        document.get("style", {}),
        "style",
        allowed_fields=frozenset(SUPPORTED_LANGUAGES),
        max_length=MAX_STYLE_LENGTH,
    )
    scripture = _parse_language_text_map(
        document.get("scripture", {}),
        "scripture",
        allowed_fields=SCRIPTURE_FIELDS,
        max_length=MAX_SCRIPTURE_LENGTH,
    )
    _check_duplicate_entries((("names", names), ("terms", terms)))

    return ChurchGlossary(
        names=names,
        terms=terms,
        style=style,
        scripture=scripture,
    )


def parse_church_glossary(raw: str | bytes | Mapping) -> ChurchGlossary:
    """Parse and validate a Church Glossary document.

    Accepts a JSON string, UTF-8 bytes, or an already-decoded mapping. Every
    problem raises ChurchGlossaryError with the offending field so a bad
    glossary never silently degrades translations.
    """
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ChurchGlossaryError(
                "Glossary is not valid UTF-8."
            ) from exc

    if isinstance(raw, str):
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ChurchGlossaryError(
                f"Glossary is not valid JSON: {exc}."
            ) from exc
    else:
        document = raw

    if not isinstance(document, Mapping):
        raise ChurchGlossaryError("Glossary must be a JSON object.")

    return _parse_document(document)


def _church_glossary_to_dict(glossary: ChurchGlossary) -> dict:
    document: dict = {}
    for section in ("names", "terms"):
        entries = getattr(glossary, section)
        if entries:
            document[section] = [
                {"japanese": entry.japanese, **entry.translations}
                for entry in entries
            ]
    if glossary.style:
        document["style"] = dict(glossary.style)
    if glossary.scripture:
        document["scripture"] = dict(glossary.scripture)
    return document


def serialize_church_glossary(glossary: ChurchGlossary) -> str:
    return json.dumps(
        _church_glossary_to_dict(glossary),
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    )


async def _get_record(session: AsyncSession, church_id: int):
    from .models import ChurchGlossaryRecord

    return (
        await session.execute(
            select(ChurchGlossaryRecord).where(
                ChurchGlossaryRecord.church_id == church_id
            )
        )
    ).scalar_one_or_none()


async def load_church_glossary(
    session: AsyncSession,
    church_id: int,
) -> ChurchGlossary | None:
    record = await _get_record(session, church_id)
    if record is None:
        return None
    try:
        return parse_church_glossary(record.content)
    except ChurchGlossaryError as exc:
        raise ChurchGlossaryError(
            f"Church Glossary for church {church_id} is invalid: {exc}"
        ) from exc


async def save_church_glossary(
    session: AsyncSession,
    church_id: int,
    glossary: ChurchGlossary,
) -> None:
    from .models import ChurchGlossaryRecord

    record = await _get_record(session, church_id)
    content = serialize_church_glossary(glossary)
    if record is None:
        session.add(
            ChurchGlossaryRecord(church_id=church_id, content=content)
        )
    else:
        record.content = content
    await session.commit()


async def delete_church_glossary(
    session: AsyncSession,
    church_id: int,
) -> bool:
    record = await _get_record(session, church_id)
    if record is None:
        return False
    await session.delete(record)
    await session.commit()
    return True


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Manage a church's own Church Glossary: names, recurring terms, "
            "target-language style, and Scripture translation preferences. "
            "This is not the project's GLOSSARY.md."
        )
    )
    parser.add_argument("--church-name", required=True)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument(
        "--file",
        type=Path,
        help="Path to a JSON Church Glossary document to validate and store.",
    )
    actions.add_argument(
        "--clear",
        action="store_true",
        help="Remove the church's stored glossary and use the defaults.",
    )
    return parser


async def _find_church(session: AsyncSession, church_name: str):
    from .models import Church

    churches = (
        (
            await session.execute(
                select(Church).where(Church.name == church_name)
            )
        )
        .scalars()
        .all()
    )
    if not churches:
        raise ChurchGlossaryError(f"No church named {church_name!r}.")
    if len(churches) > 1:
        raise ChurchGlossaryError(
            f"More than one church is named {church_name!r}. "
            "Rename or remove duplicates before managing its glossary."
        )
    return churches[0]


async def _run(args: argparse.Namespace) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from . import models

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(models.Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            church = await _find_church(session, args.church_name.strip())
            print(f"Church: {church.name} (id={church.id})")

            if args.clear:
                removed = await delete_church_glossary(session, church.id)
                print(
                    "Church Glossary: cleared"
                    if removed
                    else "Church Glossary: none stored"
                )
                return

            try:
                raw = args.file.read_text(encoding="utf-8")
            except OSError as exc:
                raise ChurchGlossaryError(
                    f"Could not read glossary file {args.file}: {exc}"
                ) from exc

            glossary = parse_church_glossary(raw)
            await save_church_glossary(session, church.id, glossary)
            print(
                "Church Glossary: updated "
                f"(names={len(glossary.names)}, "
                f"terms={len(glossary.terms)}, "
                f"style={len(glossary.style)}, "
                f"scripture={len(glossary.scripture)})"
            )
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
    except ChurchGlossaryError as exc:
        raise SystemExit(f"Glossary failed: {exc}") from exc


if __name__ == "__main__":
    main()
