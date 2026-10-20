# Kizuna — Church Live Translator

Real-time Japanese→EN/KO/ZH sermon translation. See `docs/church-live-translator-design.md` and `.scratch/church-live-translator/spec.md`.

## Run locally (Docker)

Everything is served from **one origin** (`:5173`): Vite proxies `/api` and `/ws` to the backend container, so phones on your LAN use the app without any extra configuration.

**Prerequisites:** Docker Desktop running. A `.env` next to `docker-compose.yml` with at least `GEMINI_API_KEY` and `JWT_SECRET_KEY` (`POSTGRES_*` are optional; defaults are `user`/`password`/`kizuna_db`). Optional backend settings: `GEMINI_MODEL` (default `gemini-3.8-flash`), `LOG_LEVEL` (default `INFO`), and `KIZUNA_DEBUG_DIAGNOSTICS=true` for opt-in audio-level diagnostics. Logs never include sermon text.

```bash
# First time after schema changes (e.g. the User.church_id column added in
# ticket 01): the backend only creates missing tables, it never alters an
# existing one. Reset the dev database once — this deletes dev data only.
docker compose down -v

docker compose up --build
```

Then onboard a church and operator (idempotent). This is the same command used in production:

```bash
docker compose exec backend python -m app.seed_church \
  --church-name "Kizuna Test Church" \
  --email operator@kizuna.test \
  --public-origin http://localhost:5173
```

The command prompts for a password only when one is needed. Use `--password-stdin` for automation, `--generate-password` to create one, and `--reset-password` to rotate an existing operator password. It prints the guest join URL and the operator URL.

For local development only, `curl -X POST http://localhost:8000/api/dev/seed` still creates `operator@kizuna.test / kizuna-operator-test` with QR hash `test-hash-123`.

### Church Glossary (per church)

Each church can store its own Church Glossary: Japanese names, recurring
terms, target-language style, and Scripture translation preferences. The
worker loads the glossary when the operator connects and injects it into every
translation request; reconnect to pick up changes. A church without a glossary
uses the built-in defaults (ESV / 개역개정 / 和合本 from 新共同訳).

This is **not** the project's [`GLOSSARY.md`](./GLOSSARY.md) at the repo root;
that file defines the language of this codebase.

Start from [`backend/examples/church-glossary.example.json`](./backend/examples/church-glossary.example.json)
and load it (the file path is inside the backend container):

```bash
docker compose exec backend python -m app.church_glossary \
  --church-name "Kizuna Test Church" \
  --file examples/church-glossary.example.json
```

The document accepts `names`, `terms`, `style`, and `scripture`. Every
`names`/`terms` entry needs a `japanese` source and at least one of `en`,
`ko`, `zh-hans`, or `zh-hant`. `style` and `scripture` are keyed by those same
language codes; `scripture` also accepts `source` for the Japanese Bible
translation. Entries apply only to the languages they define; an entry with no
rendering for an active language is omitted from that request. Unknown fields,
missing sources, empty values, and duplicates are rejected with a clear error
instead of being stored. Glossary text is inserted into the translation prompt,
so keep it to names, terms, style, and Scripture preferences. Run
`python -m app.church_glossary --church-name ... --clear` to remove a church's
glossary and return it to the defaults. If a stored glossary becomes invalid,
the operator stream refuses to start; re-run the CLI to see the validation
error.

**Test the full flow:**

1. On the laptop open `http://localhost:5173/operate`, log in, press **Start** (needs a microphone/aux input) or just use the QR panel.
2. To test with a **phone**, open the console at `http://<your-PC-LAN-IP>:5173/operate` (find the IP with `ipconfig`) — the QR is generated from the address you loaded the page from, so use the LAN URL or the phone will get an unreachable `localhost` link. If Windows Firewall prompts for Node/Docker, allow it.
3. Scan the QR with the phone → pick a language → you land on the listener view (waiting until the feed is live). Toggle **Audio** for browser TTS through headphones.

**Ports:** `5173` app (use this for everything), `8000` backend API directly, `5432` Postgres.

### Expose to your phone with ngrok (optional)

For testing when the phone is **not** on the same Wi-Fi. Needs a free ngrok account: copy your authtoken from [dashboard.ngrok.com](https://dashboard.ngrok.com/get-started/your-authtoken) and add it to `.env`:

```
NGROK_AUTHTOKEN=your-token-here
```

Then start the tunnel on top of the running stack:

```bash
docker compose --profile ngrok up -d
```

The public URL appears in the logs (`docker compose logs ngrok`, look for `url=https://<something>.ngrok-free.dev`). Notes:

1. Open the operator console **via that URL** (`https://<something>.ngrok-free.dev/operate`) — the QR is built from the address you loaded the page from, so a console opened on `localhost` would hand phones an unreachable link.
2. On the phone's first visit, ngrok's free tier shows a "Visit Site" warning page — tap through it.
3. `http://localhost:4040` is ngrok's request inspector: requests the phone makes through the tunnel show up there — handy when something fails.
4. The tunnel is public to anyone with the link. Stop it with `docker compose --profile ngrok stop ngrok` (or `docker compose stop ngrok`) when you're done; the rest of the stack keeps running.
