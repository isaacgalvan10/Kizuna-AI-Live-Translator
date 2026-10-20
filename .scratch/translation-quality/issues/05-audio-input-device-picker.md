# 05: Audio input device picker + line-input mode

**What to build:** The operator can choose which audio input feeds the live translation, see whether audio is arriving, and switch between the laptop microphone and a mixer or line input. The choice persists across reloads. Laptop microphone mode keeps browser speech processing on; mixer or line mode turns it off.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] The operator console lists audio input devices after microphone permission is granted.
- [x] The selected device is used for the live feed and persists across reloads.
- [x] A mixer or line-input mode disables echo cancellation, noise suppression, and automatic gain control; laptop microphone mode leaves them on.
- [x] An input level meter shows whether audio is arriving before Start.
- [x] Unplugging the selected device or denying permission produces a clear error and a usable fallback.
- [x] The captured sample rate is verified as 16 kHz; if the browser ignores the request, the operator is warned or the audio is resampled.
- [x] Tests cover device selection, persistence, mode switching, and error states.

## Comments

**2026-10-20** — Implemented and verified.

- Pure rules in `frontend/src/audio/audioInput.ts`: settings persistence (default mixer mode + system default device), device labels, mode-specific DSP constraints, streaming `Pcm16Resampler`, and RMS level.
- `useAudioInput` owns one stream/AudioContext shared by the pre-Start meter and the feed. A missing or unplugged device falls back to the system default without overwriting the saved selection; denial shows an error with Retry. Start resumes a context suspended by the autoplay policy, and a device change while live reattaches the processor.
- `AudioInputPanel` renders the picker, mode radios, meter, device/sample-rate status, alerts, and Retry. `ErrorBanner` and `focus.ts` were extracted for reuse with the existing console.
- Design conflict resolved in `docs/adr/0001-operator-selectable-audio-input.md`: mixer stays the default (Q2-B); laptop microphone is an explicit fallback.
- Verification: 145 frontend tests passing (was 120), `npm run build` and `npm run lint` clean. New coverage includes device listing, persistence across remount, DSP switching, meter signal/silence, unplug fallback before and during a live feed, denial + retry, 48 kHz resampling, suspended-context resume, and reacquisition after a failed fallback.
- Two-axis review fixes: mixer default, saved selection preserved through fallback, context resume on Start, stale stream cleared after a failed fallback, awaited persistence assertion, de-duplicated storage key/classes/messages, and the controller passed to the panel as one prop.
