import json
import sqlite3

import pytest

from app.church_glossary import main


def seed_church(db_path, *names):
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE churches ("
            "id INTEGER PRIMARY KEY, name VARCHAR, qr_code_hash VARCHAR)"
        )
        connection.executemany(
            "INSERT INTO churches (name) VALUES (?)",
            [(name,) for name in names],
        )
        connection.commit()


def stored_glossaries(db_path):
    with sqlite3.connect(db_path) as connection:
        return connection.execute(
            "SELECT church_id, content FROM church_glossaries"
        ).fetchall()


@pytest.fixture
def cli_db(tmp_path, monkeypatch):
    db_path = tmp_path / "glossary.db"
    seed_church(db_path, "Grace Church")
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
    )
    return db_path


@pytest.fixture
def glossary_file(tmp_path):
    path = tmp_path / "church-glossary.json"
    path.write_text(
        json.dumps(
            {
                "names": [
                    {"japanese": "山田牧師", "en": "Pastor Yamada"}
                ],
                "terms": [
                    {"japanese": "聖餐", "en": "Holy Communion"}
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_main_imports_a_glossary_for_an_existing_church(
    cli_db,
    glossary_file,
    capsys,
):
    main(["--church-name", "Grace Church", "--file", str(glossary_file)])

    output = capsys.readouterr().out
    assert "Church: Grace Church (id=1)" in output
    assert "names=1" in output
    assert "terms=1" in output

    rows = stored_glossaries(cli_db)
    assert len(rows) == 1
    assert rows[0][0] == 1
    stored = json.loads(rows[0][1])
    assert stored["names"][0]["japanese"] == "山田牧師"


def test_main_rejects_an_invalid_glossary_file(
    cli_db,
    tmp_path,
    capsys,
):
    path = tmp_path / "invalid.json"
    path.write_text(
        '{"names": [{"japanese": "山田牧師"}]}',
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="at least one translation"):
        main(["--church-name", "Grace Church", "--file", str(path)])

    assert stored_glossaries(cli_db) == []
    assert "Traceback" not in capsys.readouterr().err


def test_main_clear_removes_a_stored_glossary(
    cli_db,
    glossary_file,
    capsys,
):
    main(["--church-name", "Grace Church", "--file", str(glossary_file)])
    capsys.readouterr()

    main(["--church-name", "Grace Church", "--clear"])

    assert "cleared" in capsys.readouterr().out
    assert stored_glossaries(cli_db) == []


def test_main_rejects_an_unknown_church_name(cli_db, glossary_file):
    with pytest.raises(SystemExit, match="No church named 'Missing Church'"):
        main(["--church-name", "Missing Church", "--file", str(glossary_file)])


def test_main_rejects_an_ambiguous_church_name(
    tmp_path,
    monkeypatch,
    glossary_file,
):
    db_path = tmp_path / "ambiguous.db"
    seed_church(db_path, "Grace Church", "Grace Church")
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
    )

    with pytest.raises(SystemExit, match="More than one church"):
        main(["--church-name", "Grace Church", "--file", str(glossary_file)])


def test_main_requires_database_url(monkeypatch, glossary_file):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(SystemExit, match="DATABASE_URL"):
        main(["--church-name", "Grace Church", "--file", str(glossary_file)])
