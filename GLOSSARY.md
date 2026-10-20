# Church Live Translator

A real-time Japanese-to-English/Korean/Chinese translation system for church services in Osaka. This glossary is the shared language for its specs, tickets, and code.

## Language

### People

**Operator**:
The person who starts, pauses, and stops a church's live feed. Not necessarily the preacher.
_Avoid_: Preacher, admin, host, broadcaster

**Preacher**:
The person who delivers the sermon. A separate person from the operator.
_Avoid_: Minister, speaker, pastor

**Church Admin**:
The person who sets up a church's operator login. Not a system account.
_Avoid_: Superuser, account manager

**Guest**:
An attendee who joins through a QR code and follows the service on their phone.
_Avoid_: User, client

**Listener**:
A guest connected to a live feed.
_Avoid_: Viewer, audience

### Church and Tenancy

**Church**:
One congregation. Owns one QR code, one operator login, and its own live feeds.
_Avoid_: Organization, tenant, workspace

**Church Tenancy**:
Every live feed, QR code, and operator belongs to exactly one church. No church can see or control another's.
_Avoid_: Multi-tenant org, workspace

**Room**:
Where a live feed runs. A church owns its rooms; guests never choose one.
_Avoid_: Channel, session

**QR Code**:
The printed code in the pew that opens a church's language picker. Permanent for the church, not per service.
_Avoid_: Link, invite code

**Mixer**:
The sound desk that feeds sermon audio to the operator's laptop. The default audio source for the live feed; the operator can switch to the laptop microphone when the mixer feed is unavailable.
_Avoid_: Soundboard, console

### The Live Feed

**Live Feed**:
The sermon's Japanese transcript and translations, joined by listeners, under operator control.
_Avoid_: Broadcast, room stream, stream

**Live Feed State**:
One of stopped, live, or paused.
_Avoid_: Status, mode

**Feed Control**:
The operator actions on a live feed: Start, Pause, Resume, and Stop. Pause is for worship.
_Avoid_: Broadcaster, control panel

**Worship**:
The singing part of a service. The operator pauses the live feed for its duration.
_Avoid_: Praise, music set

**Sermon**:
The spoken teaching part of the service. The main content of a live feed.
_Avoid_: Message, talk

**Japanese Transcript**:
The cleaned Japanese text of the sermon. Shown to guests below the translation.
_Avoid_: Original, source text, caption

**Translation**:
The sermon text in a guest's language.
_Avoid_: Output, rendition

### Translation

**Language Channel**:
One language's stream within a live feed. Every listener of the same language shares it and receives the same translation.
_Avoid_: Language room, language feed

**Active Language Channel**:
A language channel with at least one listener. Only active channels are translated.
_Avoid_: Live language, empty room

**Transcript Timeline**:
The ordered Japanese transcript of the current live feed, shared across language channels and used to bring late listeners up to date.
_Avoid_: History buffer, transcript log

**Rolling Context**:
The last one or two Japanese Transcript lines sent with each audio chunk so consecutive translations stay coherent.
_Avoid_: History prompt, memory

**Audio Overlap**:
A short repeat of the previous audio chunk's tail at the start of the next chunk, protecting the first word after a pause. The repeated text is deduplicated before listeners see it.
_Avoid_: Crossfade, buffer overlap

**Backfill**:
The act of translating recent transcript timeline lines into a newly active language channel.
_Avoid_: History sync, catch-up

**Church Glossary**:
A church's list of names, recurring terms, preferred style, and Scripture translations used to keep wording consistent.
_Avoid_: Glossary, dictionary, terminology list

### Guest Phone

**Language Picker**:
The first screen after a QR scan. Offers English, Korean, and Chinese.
_Avoid_: Hub, landing page

**Guest Language**:
One of English, Korean, or Chinese — the languages a live feed translates into.
_Avoid_: Locale, dialect

**Listener View**:
The guest screen that shows the translation above the Japanese transcript, stacked.
_Avoid_: Guest view, side-by-side view

**Waiting**:
The listener view state before the day's live feed starts. Shows "Waiting for operator".
_Avoid_: Idle, offline

**Spoken Translation**:
The translation read aloud by the guest's phone. The Audio ON/OFF toggle controls it.
_Avoid_: TTS, playback
