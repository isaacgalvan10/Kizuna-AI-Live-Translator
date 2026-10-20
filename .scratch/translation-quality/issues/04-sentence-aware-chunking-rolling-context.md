# 04: Sentence-aware chunking + rolling context

**What to build:** Audio is flushed at natural pauses or sentence boundaries with a small overlap, and each request includes recent transcript context so translations stay coherent across chunks. A listener reading a multi-chunk passage sees complete thoughts, consistent pronouns, and stable terminology instead of chopped fragments.

**Blocked by:** 03 — Worker reliability + safe logging.

**Status:** done

- [x] Audio flushes on silence or sentence boundaries, not only a fixed timer.
- [x] Chunks have a minimum and maximum duration and a small overlap.
- [x] Overlap is deduplicated so listeners never see repeated text.
- [x] The prompt includes the previous 1–2 transcript lines (and optionally recent translations) as context.
- [x] A multi-chunk sample shows coherent sentence boundaries and consistent terminology.
- [x] Silence and noise do not produce fabricated text.
- [x] Tests cover chunk boundaries, overlap deduplication, and context inclusion.

## Comments

- **Sentence-aware chunking:** new `backend/app/audio_chunking.py` (`AudioChunker`) buffers 16 kHz/16-bit PCM and scans 20 ms frames for RMS silence (300 ≈ -40 dBFS). A pause of 0.35 s cuts the chunk at the start of the pause; if the pause starts before the 1.5 s minimum, the cut moves to the minimum. At the 5.0 s cap, the chunker prefers the latest pause of at least 0.15 s inside the chunk over a blind mid-speech cut. The next chunk carries a 0.3 s tail overlap so the model does not lose the first word after a boundary. The worker's flusher tick moved from 3.0 s to 0.2 s so a detected pause is sent promptly instead of waiting for the old fixed timer.
- **Silence/noise gate:** each segment records how many leading bytes are overlap. `contains_new_speech` ignores that prefix and requires at least 0.2 s of non-silent frames before any API call. Silence and short blips are dropped without a request, and the prompt already instructs the model to return empty strings and ignore non-speech.
- **Overlap deduplication:** new `backend/app/transcript_text.py` removes the longest exact suffix/prefix match (2-character minimum, 40-character cap) between the previous line and the new output. It runs on the Japanese transcript and on each language's translation. If the Japanese chunk is entirely repeated, nothing is broadcast. The prompt also tells the model that the audio may start with an overlap and must not repeat context.
- **Rolling context:** the worker keeps the last two deduplicated Japanese lines in a `deque(maxlen=2)` and passes them as `context_lines` to `GeminiTranslator.translate`. The prompt's RECENT CONTEXT section now says the lines are for continuity and terminology (not re-translation), warns about the audio overlap, and asks for names/terms to stay consistent with that context. Per-language last translations are also kept so overlap can be removed from translations.
- **Failure semantics:** audio is still removed before the request and never requeued; a failed or repeated-only chunk is not re-sent. When no language is active, the buffer, overlap marker, and last translations are cleared.
- **Verification:** 11 new chunker tests (minimum hold, pause cut, max cap, short-pause preference at the cap, pause split across feeds, pre-minimum pause, overlap prefix, clear, silence/blip/overlap-only gating), 9 dedupe tests, 7 new worker tests (silence skip, no broadcast when the model returns an empty transcript for noise, context inclusion, two-line trimming, Japanese+translation dedupe, overlap-only skip, three-chunk passage), and 2 prompt tests. Full backend suite: 138 passed (was 109); `compileall` clean. No live Gemini call was made: the multi-chunk and noise criteria are verified at the pipeline level with a scripted model, while model coherence on real sermon audio is ticket 08 by design (it runs this same chunker).
- **Remaining:** the 0.35 s / 0.15 s / 300 RMS tuning and 1.5 s / 5.0 s bounds are heuristics that ticket 08 should calibrate against real sermon audio and p95 latency. Dedupe is exact-match only: if the model paraphrases the overlapping words differently, they will not be removed (the prompt is the mitigation), and a genuinely repeated short phrase can be mistaken for overlap. Chunk production is not backpressured: if calls repeatedly run near the 8 s retry budget, audio can queue faster than it drains; ticket 08 should measure this and a drop/backpressure policy can be added if needed.
