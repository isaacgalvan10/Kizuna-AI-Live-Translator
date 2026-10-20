import json

import pytest
from sqlalchemy import text

from app.church_glossary import (
    ChurchGlossary,
    ChurchGlossaryEntry,
    ChurchGlossaryError,
    load_church_glossary,
    parse_church_glossary,
    save_church_glossary,
    serialize_church_glossary,
)
from app.models import Church

FULL_GLOSSARY = {
    "names": [
        {
            "japanese": "山田牧師",
            "en": "Pastor Yamada",
            "ko": "야마다 목사",
            "zh-hans": "山田牧师",
        }
    ],
    "terms": [
        {
            "japanese": "聖餐",
            "en": "Holy Communion",
            "ko": "성찬",
            "zh-hans": "圣餐",
        }
    ],
    "style": {
        "en": "Use short, warm sentences.",
        "ko": "Use short sentences in formal polite style.",
    },
    "scripture": {
        "source": "新改訳2017",
        "en": "NIV",
        "ko": "새번역",
        "zh-hans": "和合本修订版",
    },
}


def test_parse_church_glossary_reads_names_terms_style_and_scripture():
    glossary = parse_church_glossary(FULL_GLOSSARY)

    assert glossary.names == (
        ChurchGlossaryEntry(
            japanese="山田牧師",
            translations={
                "en": "Pastor Yamada",
                "ko": "야마다 목사",
                "zh-hans": "山田牧师",
            },
        ),
    )
    assert glossary.terms[0].translations["en"] == "Holy Communion"
    assert glossary.style == {
        "en": "Use short, warm sentences.",
        "ko": "Use short sentences in formal polite style.",
    }
    assert glossary.scripture == {
        "source": "新改訳2017",
        "en": "NIV",
        "ko": "새번역",
        "zh-hans": "和合本修订版",
    }
    assert glossary.is_empty is False


def test_parse_church_glossary_accepts_json_text_and_normalizes_whitespace():
    raw = json.dumps(
        {
            "names": [
                {"japanese": "  山田 牧師 ", "en": " Pastor\nYamada "}
            ]
        },
        ensure_ascii=False,
    )

    glossary = parse_church_glossary(raw)

    assert glossary.names[0].japanese == "山田 牧師"
    assert glossary.names[0].translations["en"] == "Pastor Yamada"


def test_parse_church_glossary_allows_an_empty_glossary():
    glossary = parse_church_glossary({})

    assert glossary == ChurchGlossary()
    assert glossary.is_empty is True


def test_parse_church_glossary_rejects_invalid_json():
    with pytest.raises(ChurchGlossaryError, match="not valid JSON"):
        parse_church_glossary("{not json")


def test_parse_church_glossary_rejects_a_non_object_document():
    with pytest.raises(ChurchGlossaryError, match="JSON object"):
        parse_church_glossary("[]")


def test_parse_church_glossary_rejects_unknown_top_level_fields():
    with pytest.raises(ChurchGlossaryError, match="Unknown glossary field 'term'"):
        parse_church_glossary({"term": []})


def test_parse_church_glossary_rejects_a_non_list_entries_section():
    with pytest.raises(ChurchGlossaryError, match="'names' must be a list"):
        parse_church_glossary({"names": {}})


def test_parse_church_glossary_rejects_an_entry_without_japanese():
    with pytest.raises(ChurchGlossaryError, match="names\\[0\\].japanese"):
        parse_church_glossary({"names": [{"en": "Pastor Yamada"}]})


def test_parse_church_glossary_rejects_an_entry_without_translations():
    with pytest.raises(ChurchGlossaryError, match="at least one translation"):
        parse_church_glossary({"names": [{"japanese": "山田牧師"}]})


def test_parse_church_glossary_rejects_an_unsupported_language():
    with pytest.raises(ChurchGlossaryError, match="'fr' is not supported"):
        parse_church_glossary({"names": [{"japanese": "山田牧師", "fr": "Pasteur"}]})


def test_parse_church_glossary_rejects_an_empty_translation():
    with pytest.raises(ChurchGlossaryError, match="names\\[0\\].en"):
        parse_church_glossary({"names": [{"japanese": "山田牧師", "en": "   "}]})


def test_parse_church_glossary_rejects_duplicate_entries():
    with pytest.raises(ChurchGlossaryError, match="Duplicate glossary entry '聖餐'"):
        parse_church_glossary(
            {
                "names": [{"japanese": "聖餐", "en": "Holy Communion"}],
                "terms": [{"japanese": "聖餐", "en": "Communion"}],
            }
        )


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ({"style": []}, "'style' must be an object"),
        ({"style": {"fr": "Short."}}, "'fr' is not supported"),
        ({"style": {"en": "   "}}, "style.en"),
        (
            {"scripture": {"esv": "ESV"}},
            "Unknown Scripture field 'esv'",
        ),
        (
            {"scripture": {"en": "   "}},
            "scripture.en",
        ),
    ],
)
def test_parse_church_glossary_rejects_invalid_style_and_scripture(document, message):
    with pytest.raises(ChurchGlossaryError, match=message):
        parse_church_glossary(document)


def test_serialize_church_glossary_round_trips():
    glossary = parse_church_glossary(FULL_GLOSSARY)

    reparsed = parse_church_glossary(serialize_church_glossary(glossary))

    assert reparsed == glossary


async def make_church(db_session, name="Grace Church") -> Church:
    church = Church(name=name)
    db_session.add(church)
    await db_session.commit()
    await db_session.refresh(church)
    return church


async def test_load_church_glossary_returns_none_without_a_stored_glossary(db_session):
    church = await make_church(db_session)

    assert await load_church_glossary(db_session, church.id) is None


async def test_save_and_load_church_glossary_round_trips(db_session):
    church = await make_church(db_session)
    glossary = parse_church_glossary(FULL_GLOSSARY)

    await save_church_glossary(db_session, church.id, glossary)

    assert await load_church_glossary(db_session, church.id) == glossary


async def test_save_church_glossary_replaces_the_existing_glossary(db_session):
    church = await make_church(db_session)
    first = parse_church_glossary(FULL_GLOSSARY)
    second = parse_church_glossary(
        {"terms": [{"japanese": "恵み", "en": "grace"}]}
    )

    await save_church_glossary(db_session, church.id, first)
    await save_church_glossary(db_session, church.id, second)

    assert await load_church_glossary(db_session, church.id) == second


async def test_glossary_is_scoped_to_its_church(db_session):
    first = await make_church(db_session, "First Church")
    second = await make_church(db_session, "Second Church")
    glossary = parse_church_glossary(FULL_GLOSSARY)

    await save_church_glossary(db_session, first.id, glossary)

    assert await load_church_glossary(db_session, second.id) is None


async def test_load_church_glossary_rejects_invalid_stored_content(db_session):
    church = await make_church(db_session)
    await db_session.execute(
        text(
            "INSERT INTO church_glossaries (church_id, content) "
            "VALUES (:church_id, :content)"
        ),
        {
            "church_id": church.id,
            "content": '{"names": [{"japanese": "山田牧師"}]}',
        },
    )
    await db_session.commit()

    with pytest.raises(
        ChurchGlossaryError,
        match=f"church {church.id}.*at least one translation",
    ):
        await load_church_glossary(db_session, church.id)

