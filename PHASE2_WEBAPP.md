# Phase 2: Web App, Admin Panel, AI Weight Tuning, Render Deployment

This phase adds an actual deployable service on top of the phase-1
structural refactor. It does **not** yet touch the multi-strategy
signal-generation engine itself (still phase-3 work — see the end of
`MIGRATION.md`).

## What was built

- **`admin/`** — FastAPI app + Jinja2/HTMX admin panel. Single shared
  password (`ADMIN_PASSWORD` env var), signed session cookie. Pages:
  dashboard (weights + recent signals), weight adjustment log. Run AI
  review on demand from the dashboard; edit any weight manually too.
- **`api/`** — JSON endpoints: `GET /api/signals`, `GET
  /api/strategies/weights`, `POST /api/strategies/review`, `GET
  /api/health`. Read-only today except the review trigger.
- **`database/db.py` + `database/models.py`** — SQLAlchemy models
  (`SignalRecord`, `StrategyWeight`, `WeightAdjustmentLog`) and a
  session helper. Works against Render's managed Postgres
  (`DATABASE_URL`) or falls back to local SQLite if unset.
- **`ai/openrouter_client.py`** — thin OpenRouter wrapper. Model is one
  env var (`OPENROUTER_MODEL`); start on a `:free` model, switch to a
  paid one later with no code changes.
- **`ai/accuracy_reviewer.py`** — the weight-tuning job you asked for.
  **Guardrails, not optional:**
  - Won't touch a strategy until it has `AI_MIN_SAMPLES_FOR_ADJUSTMENT`
    (default 20) closed signals — small samples are noise.
  - Caps any single adjustment to `AI_MAX_WEIGHT_STEP_PCT` (default
    ±20%) of the current weight.
  - Always clamps the result to that strategy's configured
    `[min_weight, max_weight]`.
  - Every adjustment — before/after weight, sample size, win rate, and
    the AI's stated reasoning — is written to `WeightAdjustmentLog`.
    Nothing changes silently, and you can read the reasoning in
    `/admin/logs`.
- **`ai/signal_explainer.py`** — optional plain-language explanation of
  a signal, for Discord alerts / admin panel. Not wired into
  `alerts/discord_alerts.py` yet (see "Not done" below).
- **`Dockerfile`** — Render's native Python buildpack can't install the
  `TA-Lib` C library that `indicators/features.py` depends on, so this
  service needs to deploy via Docker. The Dockerfile compiles TA-Lib
  from source, then installs `requirements.txt`.
- **`render.yaml`** — one web service (Docker runtime) + one managed
  Postgres instance, wired together via `DATABASE_URL`.

## What's NOT done yet (be aware before you deploy expecting live signals)

1. **The scanner isn't wired to write `SignalRecord` rows.**
   `signals/generator.py` (the original single-model logic, untouched)
   still runs standalone via `cli/main.py`; it doesn't call into the new
   database layer or Discord through this app yet. Until that's wired,
   the admin panel will show an empty signals table and the AI reviewer
   will have nothing to adjust (it'll report `skipped_low_sample` for
   `ml_model`, seeded at weight 1.0 on first boot).
2. **`ai/signal_explainer.py` isn't called from anywhere.** It's ready
   to use once signals are flowing.
3. **No background scheduler yet.** Running the scanner and the AI
   review pass on a timer (rather than only via the admin button / API
   call) needs either an in-process scheduler or — better, so a stuck
   scan can't take the admin panel down — a separate Render **Cron Job**
   or **Background Worker** hitting the same Postgres database. Worth
   deciding once you see how heavy scans get.
4. **`strategies/base.py` / `core/types.py` still aren't used.** The ML
   model isn't wrapped as a `Strategy` plugin yet, so `StrategyWeight`
   for `ml_model` doesn't yet feed into how a signal actually gets
   generated — the AI can tune its weight, but nothing reads that weight
   yet. That's the natural next step: wrap the model, build the
   aggregator, have it read `StrategyWeight.weight` per strategy when
   combining opinions.

## Deploying

1. Push this repo to your new GitHub repo.
2. Create a database on [Neon](https://neon.tech) (free tier) and copy its
   connection string.
3. On Render: **New > Blueprint**, point it at the repo — it'll read
   `render.yaml` and provision the web service.
4. Set the `sync: false` env vars in the Render dashboard (they're not
   auto-generated): `DATABASE_URL` (your Neon connection string),
   `ADMIN_PASSWORD`, `DISCORD_WEBHOOK`, `OPENROUTER_API_KEY`.
   `SECRET_KEY` is generated automatically by the blueprint.
5. First deploy will build the Docker image (TA-Lib compiles from
   source — expect the first build to take a few minutes longer than
   subsequent ones).
6. Visit `/admin`, log in with `ADMIN_PASSWORD`.

## Local dev

```
cp .env.example .env   # fill in SECRET_KEY, ADMIN_PASSWORD at minimum
pip install -r requirements.txt
uvicorn admin.server:app --reload
```

No `DATABASE_URL` needed locally — it falls back to a `cryptosight.db`
SQLite file in the project root (gitignored).
