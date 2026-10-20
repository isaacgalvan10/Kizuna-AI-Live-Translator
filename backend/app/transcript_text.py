MAX_OVERLAP_CHARS = 40
MIN_OVERLAP_CHARS = 2


def dedupe_overlap(previous: str, current: str) -> str:
    """Drops text at the start of ``current`` that repeats the tail of ``previous``.

    The audio chunks share a short overlap, so the model can transcribe the last
    few words of the previous chunk again. The longest exact suffix/prefix
    match is removed. A one-character match is ignored because it is usually
    punctuation rather than repeated speech.
    """

    if not previous or not current:
        return current.strip()

    max_length = min(len(previous), len(current), MAX_OVERLAP_CHARS)
    for size in range(max_length, MIN_OVERLAP_CHARS - 1, -1):
        if previous.endswith(current[:size]):
            return current[size:].strip()
    return current.strip()
