# 08: Evaluation harness + golden set

**What to build:** A repeatable offline evaluation runs real sermon audio through the same chunker and prompt as production, scores the Japanese transcript and translations, and records latency and cost. It produces a golden set and a report that can compare models and prompt variants.

**Blocked by:** 03 — Worker reliability + safe logging; 04 — Sentence-aware chunking + rolling context; 06 — Church Glossary.

**Status:** ready-for-agent

- [ ] The evaluation area has a manifest, audio and reference layout, and a runner.
- [ ] The runner uses the same chunker and prompt builder as production.
- [ ] It records model, prompt variant, latency, input/output/thinking tokens, estimated cost, and outputs per chunk.
- [ ] It computes Japanese character error rate against a reference transcript.
- [ ] It supports human and LLM ratings for faithfulness, fluency, terminology, and Scripture accuracy.
- [ ] It runs on 20–30 minutes of real audio covering a Scripture reading, names, English code-switching, and fast or quiet speech.
- [ ] Results are written to JSON or CSV for comparison.
- [ ] A baseline result for the current pipeline is recorded.
