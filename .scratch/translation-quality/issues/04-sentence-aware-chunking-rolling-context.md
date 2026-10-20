# 04: Sentence-aware chunking + rolling context

**What to build:** Audio is flushed at natural pauses or sentence boundaries with a small overlap, and each request includes recent transcript context so translations stay coherent across chunks. A listener reading a multi-chunk passage sees complete thoughts, consistent pronouns, and stable terminology instead of chopped fragments.

**Blocked by:** 03 — Worker reliability + safe logging.

**Status:** ready-for-agent

- [ ] Audio flushes on silence or sentence boundaries, not only a fixed timer.
- [ ] Chunks have a minimum and maximum duration and a small overlap.
- [ ] Overlap is deduplicated so listeners never see repeated text.
- [ ] The prompt includes the previous 1–2 transcript lines (and optionally recent translations) as context.
- [ ] A multi-chunk sample shows coherent sentence boundaries and consistent terminology.
- [ ] Silence and noise do not produce fabricated text.
- [ ] Tests cover chunk boundaries, overlap deduplication, and context inclusion.
