# 02: Shared Live Feed State visuals module

**What to build:** One module owns how each Live Feed State looks, so the Listener View and Operator Console can never drift apart. For every state — the listener's Waiting/Live/Paused/Ended and the console's Stopped/Live/Paused — it exposes the label, pill styling, and dot styling; the console's "Stopped" versus the listener's "Ended" for the same underlying state is explicit shared data, not duplication. All styling references the theme utilities added in ticket 01 (no literal colour values), and the module ships the completeness/consistency unit test from the spec's Testing Decisions. The two views start consuming it in tickets 04 and 05 — this ticket does not restyle them.

**Blocked by:** 01-theme-foundation

**Status:** ready-for-agent

- [ ] Module exposes label + pill + dot presentation for every state either view can render (Waiting, Live, Paused, Ended, Stopped)
- [ ] The Ended/Stopped label difference is explicit data in the module
- [ ] Unit test: every entry complete and non-empty; labels match the strings the views use today
- [ ] Styling references theme utilities only (no literal colour values)
- [ ] All existing tests, lint, and `tsc -b` build pass
