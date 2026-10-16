# Church Live Translator Spec

Status: ready-for-agent

## Problem Statement

Japanese Christian churches in Osaka need a real-time AI translation system for their services. Attendees who don't speak Japanese (English, Korean, Chinese speakers) cannot follow the sermon. The current Kizuna app has a landing page that exposes operator controls (room ID input, Broadcaster button) to guests, uses the operator's device microphone (picking up congregation noise), and lacks a pause mechanism for worship music. The system must: transcribe Japanese audio (with occasional English words and multiple speakers), show translations stacked on mobile, let attendees listen via headphones on their own phones, pause during worship, and join by scanning a QR code after an operator starts the live feed.

## Solution

A real-time translation system where:
- **Operator** (volunteer at sound booth) connects laptop to church mixer via aux cable, opens a bookmarked operator URL, clicks **Start Live Feed** to begin streaming audio to the backend.
- **Guests** scan a pew QR code → land on a language picker (English, Korean, Chinese) → pick one → enter listener view showing Japanese transcript stacked above translation → enable headphone audio via browser TTS.
- **During worship**, operator clicks **Pause** on the operator URL → transcription stops, listener view shows "Paused", TTS cancels. Operator clicks **Resume** when sermon resumes.
- **Church tenancy** is enforced via `church_id` on all operators, rooms, and QR codes; a second church gets isolated data.

## User Stories

1. As an **operator**, I want to open a bookmarked URL on the mixer laptop and click **Start Live Feed**, so that the sermon audio begins streaming to the backend without typing credentials.
2. As an **operator**, I want to click **Pause** during worship music and **Resume** when the sermon continues, so that guests don't hear songs translated over their headphones.
3. As an **operator**, I want to click **Stop** after the service ends, so that the live feed ends cleanly.
4. As a **guest**, I want to scan a QR code on my phone and immediately see a language picker (English, Korean, 繁體中文), so I can choose my language without entering a room ID.
5. As a **guest**, I want to pick a language and land on the listener view showing Japanese transcript stacked above the translation, so I can follow along visually.
6. As a **guest**, I want to toggle **Audio: ON** and hear the translation via my phone's browser TTS in my chosen language, so I can listen on headphones.
7. As a **guest**, if I scan the QR before the operator starts, I want to pick my language and wait on the listener view with a "Waiting for operator" message, so I don't need to scan again when the service begins.
8. As a **guest**, when the operator pauses, I want to see a "Paused" banner and have TTS stop, so I know the feed is intentionally stopped.
9. As a **church admin**, I want to create a shared operator login (email + password) for this church, so volunteers can log in on the mixer laptop without per-person accounts.
10. As a **church admin**, I want a second church to have its own QR code, operator login, and live feed, completely isolated from the first church, so multiple churches can use the system independently.

## Implementation Decisions

### Modules & Interfaces

**Backend (FastAPI + SQLAlchemy + WebSockets)**
- **Church tenancy**: Add `church_id` column to `User` model (nullable for guests). Scope all operator queries by `church_id`.
- **Operator auth**: New `/api/operator/login` endpoint accepting email/password, returning JWT with `church_id` claim. Protect `/ws/stream/{room_id}` and operator control endpoints with this auth.
- **Live feed control**: Add `is_live` toggle on `Room` (already exists). Operator POST `/api/operator/rooms/{room_id}/start`, `/pause`, `/stop` to control feed state. Broadcast `feed_state` events to listeners via WebSocket.
- **QR join API**: `POST /api/join/{qr_code_hash}` returns `is_live`, `room_id`, `church_name`. Resolves to the church's live room when one is running and its first room otherwise (room_id is null only when the church has no room), so a guest who scans before the feed starts can already wait.
- **Audio source**: Operator laptop captures from mixer aux via `getUserMedia` (existing `/preacher` route already does this). No backend change.
- **TTS**: Browser `speechSynthesis` on listener (existing). Server TTS not implemented; fallback documented only.

**Frontend (React + Vite + Tailwind)**
- **Route split**:
  - `/` → **Guest QR landing** (new): language picker only, no room ID, no Broadcaster button. POSTs to `/api/join/{qr_hash}`, then navigates to `/listen/{room_id}/{lang}`.
  - `/listen/{room_id}/{lang}` → **Listener view** (refactor existing `/listener`): stacked layout (translation top, Japanese bottom), "Waiting for operator" state when `is_live=false`, "Paused" banner on `feed_state=paused`, Audio ON/OFF toggle using browser TTS.
  - `/operate` → **Operator console** (new, separate from guest routes): login form → Start/Pause/Stop buttons, status indicator. Bookmarkable URL. No guest access.
  - `/preacher` → **Deprecated/removed** (replaced by `/operate`).
- **Listener view layout**: Stacked on mobile (translation full-width, Japanese scrolling below). Desktop stays two-pane (existing `md:grid-cols-2`).
- **TTS handling**: Cancel on Pause, on language change, on Audio OFF. Primer utterance on Audio ON (existing pattern).

### Data Model Changes
- `User.church_id` (Integer, ForeignKey to `churches.id`, nullable=True for guests)
- `Room` already has `church_id` and `is_live`
- No new tables needed for MVP

### API Contracts
- `POST /api/operator/login` → `{ access_token, token_type, church_id }`
- `POST /api/operator/rooms/{room_id}/start` (auth required) → `{ status: "live" }`
- `POST /api/operator/rooms/{room_id}/pause` (auth required) → `{ status: "paused" }`
- `POST /api/operator/rooms/{room_id}/stop` (auth required) → `{ status: "stopped" }`
- WebSocket `ws://host/ws/listen/{room_id}/{lang}`: receives `{ type: "live_translation", data: { original, translation } }` and `{ type: "feed_state", data: "live" | "paused" | "stopped" }`

### Seams for Testing
1. **Operator auth seam**: `POST /api/operator/login` — test with valid/invalid credentials, verify JWT contains correct `church_id`.
2. **Feed control seam**: `POST /api/operator/rooms/{room_id}/{start|pause|stop}` — test state transitions, verify WebSocket broadcasts to listeners.
3. **QR join seam**: `POST /api/join/{qr_code_hash}` — test returns correct `is_live`/`room_id` for live vs not-yet-started rooms.
4. **Listener WebSocket seam**: `ws://host/ws/listen/{room_id}/{lang}` — test receives translation messages and feed_state events.
5. **TTS seam**: Browser `speechSynthesis` — test Audio ON/OFF, language voice selection, cancellation on Pause.

## Testing Decisions

- **What makes a good test**: Test external behavior (API responses, WebSocket messages, UI state) not implementation details. Use integration tests for seams above.
- **Modules to test**:
  - Backend: operator auth endpoints, feed control endpoints, QR join endpoint, WebSocket broadcast logic.
  - Frontend: Guest QR landing → language picker → listener view flow; operator login → Start/Pause/Stop flow; listener view stacked layout on mobile; TTS toggle and Pause cancellation.
- **Prior art**: Existing WebSocket tests in backend (if any), React component tests in frontend (if any). Follow patterns in `backend/app/test.py` and frontend test setup.

## Out of Scope

- Automatic music detection for pause/resume (deferred per Q3)
- Per-volunteer operator accounts (deferred per Q7)
- Server-side TTS (deferred per Q9 — only if browser voices fail real-device testing)
- Simplified Chinese language support (deferred per Q5)
- Admin UI for creating churches/operators (manual DB seed or CLI for MVP)
- HTTPS/WSS for production (assume LAN HTTP for Osaka Sunday)

## Further Notes

- **Seam count**: The design targets **one primary seam** — the WebSocket connection between operator audio stream and listener translation feed. Feed control (Start/Pause/Stop) is a second seam but simple state machine.
- **Risk mitigations**: Shared operator login (Q7-A) accepted for MVP; rotate password post-Sunday. Operator URL bookmark (Q4-A) sent via LINE/email to substitutes. Browser TTS tested on real iOS/Android devices before Sunday.
- **Existing code reuse**: `/preacher` route → `/operate` console. `/listener` route → refactor to stacked layout + waiting/paused states. `POST /api/join/{qr_code_hash}` unchanged. `GeminiWorker` unchanged.