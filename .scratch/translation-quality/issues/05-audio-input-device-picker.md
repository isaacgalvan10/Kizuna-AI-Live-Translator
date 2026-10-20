# 05: Audio input device picker + line-input mode

**What to build:** The operator can choose which audio input feeds the live translation, see whether audio is arriving, and switch between the laptop microphone and a mixer or line input. The choice persists across reloads. Laptop microphone mode keeps browser speech processing on; mixer or line mode turns it off.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] The operator console lists audio input devices after microphone permission is granted.
- [ ] The selected device is used for the live feed and persists across reloads.
- [ ] A mixer or line-input mode disables echo cancellation, noise suppression, and automatic gain control; laptop microphone mode leaves them on.
- [ ] An input level meter shows whether audio is arriving before Start.
- [ ] Unplugging the selected device or denying permission produces a clear error and a usable fallback.
- [ ] The captured sample rate is verified as 16 kHz; if the browser ignores the request, the operator is warned or the audio is resampled.
- [ ] Tests cover device selection, persistence, mode switching, and error states.
