# 09: Model/prompt A/B + default selection

**What to build:** Compare `gemini-3.8-flash` (low thinking) with `gemini-3.5-flash-lite` on the golden set, then compare the improved prompt and Church Glossary against the current prompt with the winning model. Choose the production default based on accuracy first, latency second, and cost third.

**Blocked by:** 08 — Evaluation harness + golden set.

**Status:** ready-for-agent

- [ ] Both models run on the same golden set with the same prompt.
- [ ] The prompt and glossary ablation runs with the winning model.
- [ ] The report includes p50/p95 latency, Japanese CER, faithfulness, fluency, terminology, Scripture accuracy, and cost.
- [ ] The decision rule is applied: faithfulness first, p95 latency over 8 seconds is a hard failure, cost is a tiebreaker.
- [ ] The chosen model and prompt are set as the production default.
- [ ] The report and raw outputs are stored for future regression checks.
