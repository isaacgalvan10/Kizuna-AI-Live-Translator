from app.transcript_text import dedupe_overlap


def test_removes_a_full_repeated_sentence():
    assert (
        dedupe_overlap("神は愛です。", "神は愛です。次の文です。")
        == "次の文です。"
    )


def test_removes_a_partial_repeated_tail():
    assert (
        dedupe_overlap("神は愛です。", "です。次の文です。")
        == "次の文です。"
    )


def test_keeps_text_that_does_not_overlap():
    current = "人は罪を犯しました。"

    assert dedupe_overlap("神は愛です。", current) == current


def test_removes_overlap_in_a_spaced_language():
    assert (
        dedupe_overlap(
            "God is love.",
            "God is love. We are his children.",
        )
        == "We are his children."
    )


def test_ignores_a_single_character_overlap():
    assert dedupe_overlap("はい。", "。次へ") == "。次へ"


def test_returns_empty_when_the_whole_chunk_is_repeated():
    assert dedupe_overlap("God is love.", "is love.") == ""


def test_caps_the_removed_overlap():
    previous = "a" * 200
    current = "a" * 200

    assert dedupe_overlap(previous, current) == "a" * 160


def test_trims_whitespace_around_the_result():
    assert dedupe_overlap("God is love.", "God is love.  ") == ""


def test_strips_current_when_there_is_no_previous():
    assert dedupe_overlap("", "  God is love.  ") == "God is love."
