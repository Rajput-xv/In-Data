# In-Data

I built this as the Breathe ESG Tech Intern assignment. It's a small Django + React app that ingests carbon-relevant activity data from three source shapes (SAP, utility portal, corporate travel), normalizes it into one activity table, flags suspicious rows, and lets an analyst approve them before they lock for audit.

The brief is clear that the hard part isn't computing carbon - it's that every client's data lives somewhere different, in a different shape, with different gaps. The data model and the validator are where I put the thought.

## What's here

- **`backend/`** - Django 5 + DRF, three apps (`ingestion`, `normalize`, `review`), SQLite local / Postgres on Render.
- **`frontend/`** - Vite + React 19 + Tailwind 4, plain JSX, hand-rolled UI.
- **`backend/sample_data/`** - one realistic file per source, each carrying three+ flag scenarios.
- **`docs/`** - `MODEL.md`, `DECISIONS.md`, `TRADEOFFS.md`, `SOURCES.md`.
- **`PROJECT_PLAN.md`** - the short plan I wrote on day zero.

## Run locally

Prereqs: Python 3.12+, Node 20+.

```bash
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000

# frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Both `.env` files ship with LOCAL credentials active and PROD commented out. Swap the comments when deploying.

**Sign-in.** The SPA gates on `/` with a single allow-listed analyst email. Use the value of `VITE_ANALYST_EMAIL` from `frontend/.env` (default `automation@indata.com`). Wrong email → inline error. Right email → it lands in `sessionStorage`, the navbar shows it on every page, and every API call ships it as `X-Analyst-Email`. Close the tab or click the `✕` on the analyst pill to sign out.

## Source decisions

| Source | Mechanism | Why |
|---|---|---|
| SAP fuel / procurement | Semicolon-CSV upload | Enterprise IT doesn't grant SAP Gateway access during onboarding. The realistic deliverable is an `SE16N` / `SQ01` dump emailed in. |
| Utility (electricity) | Portal CSV upload | PDF parsing is fragile across providers; commercial APIs are rare. Portal CSV is what facilities teams click each month. |
| Corporate travel | Concur-shaped JSON upload | Concur OAuth is multi-week partner approval. I matched the v3 Expense response shape so swapping to a real poller later is one wrapper change. |

Full per-source research, sample-data tricks, and failure modes in [docs/SOURCES.md](docs/SOURCES.md).

## Data model

- **`IngestionBatch`** - one upload event.
- **`RawRecord`** - verbatim row payload, never mutated (audit trail).
- **`NormalizedActivity`** - one unified row per source row, with `activity_type`, `scope`, canonical `quantity` + `unit`, period range, location, status.
- **`ActivityFlag`** - why a row looks suspicious. Eight validator rules populate this.
- **`ApprovalAction`** - who decided what and when. Approve/reject both lock the row from further edits.

Full table layout, why each table earns its place, multi-tenancy plan, and Scope 1/2/3 handling in [docs/MODEL.md](docs/MODEL.md).

## The eight validator rules

| Code | Severity | Triggers when |
|---|---|---|
| `UNIT_UNKNOWN` | error | Unit not in `normalize/units.py` table. |
| `UNIT_RANGE` | warning | Quantity outside the plausible band for the activity type. |
| `QUANTITY_NONPOSITIVE` | error | qty ≤ 0. |
| `PERIOD_INVALID` | error | end < start or > 90 days. |
| `PERIOD_OVERLAP` | warning | Overlaps an APPROVED row at the same location. |
| `LOOKUP_MISSING` | warning | Plant code / IATA code not in the lookup. |
| `CURRENCY_MISMATCH` | warning | Amount currency ≠ EUR with no FX rate. |
| `DUPLICATE_LIKELY` | warning | Same `source_ref` exists in another batch. |

Errors require an explicit override note at approve time. Warnings don't.

## API surface

```
POST  /api/ingest/{sap|utility|travel}/   multipart file upload
GET   /api/batches/                       list batches
GET   /api/batches/{id}/                  batch detail with counts
GET   /api/activities/?status=&source=&batch=&activity_type=&scope=
GET   /api/activities/{id}/               detail with flags + raw payload
POST  /api/activities/{id}/approve/       body: {"note": "..."}
POST  /api/activities/{id}/reject/        body: {"note": "..."}
```

## What I deliberately didn't build

- No Celery / async pipeline. Sync ingest is fine at prototype scale.
- No real auth - single-email gate, see Sign-in above. Real version uses SSO.
- No emission-factor calculation. I store the inputs cleanly; the math is downstream.
- No PDF ingestion. Portal CSV is what facilities teams actually click.
- No multi-tenant scoping. One client per the brief.

Long form in [docs/TRADEOFFS.md](docs/TRADEOFFS.md).

## Deployment

- **Backend → Render** via `backend/render.yaml`. Includes a managed Postgres on the free tier.
- **Frontend → Vercel** via `frontend/vercel.json`. SPA rewrites all paths to `index.html`. Set `VITE_API_BASE` in the Vercel project to the Render URL.

## Sample data

Three files in `backend/sample_data/`. Each is hand-written to match the shape I researched and deliberately trips three+ distinct validator rules so the dashboard has interesting cases to look at. Trick-by-trick breakdown in [docs/SOURCES.md](docs/SOURCES.md).
