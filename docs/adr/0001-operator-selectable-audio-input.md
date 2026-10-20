# 0001: Operator-selectable audio input

- **Status:** Accepted
- **Date:** 2026-10-20

## Context

The original design (Q2-B in `docs/church-live-translator-design.md`) locked the live feed to the church mixer's aux/line output and rejected the operator laptop microphone because it picks up singing, clapping, and the congregation. Translation-quality ticket 05 adds an input-device picker so the operator can select whichever interface is actually connected to the laptop, with the laptop microphone available when the mixer feed is unavailable.

## Decision

- The operator console lists audio inputs and persists the selected device and mode across reloads.
- Mixer / line mode is the default and disables echo cancellation, noise suppression, and automatic gain control.
- Laptop microphone mode leaves the browser's speech processing on.
- If the saved device is missing or disconnects, the current session falls back to the system default input and shows a notice; the saved selection is not overwritten, so a reload retries the operator's device.

## Consequences

- Q2-B remains the recommended deployment: the mixer is still the default source, and the worship-noise risk of a laptop microphone is unchanged when the operator deliberately chooses it.
- No backend contract change: both modes deliver 16 kHz, 16-bit mono PCM over the existing stream socket.
- A missing device costs one failed `getUserMedia` attempt before the default input is used.
