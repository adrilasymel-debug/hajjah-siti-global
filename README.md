# HAJJAH SITI GLOBAL · Business Management

A modern internal business workspace for HAJJAH SITI GLOBAL, a dried seafood business. Built from scratch with a React frontend, FastAPI API, PostgreSQL production database, private document storage and a separate invoice-processing worker.

## What is implemented

- Owner dashboard with real outstanding balances, review queue, overdue invoices, purchasing trend, expected-invoice alerts and recent activity.
- Password-hashed accounts, revocable server-side sessions, CSRF checks, owner/staff access, permission-aware navigation and backend ownership enforcement.
- Suppliers, profiles, linked bills, payments and outstanding balances.
- Invoice upload, file validation, private originals, built-in paginated PDF/image preview, editable fields and line items, duplicate warnings, human verification, owner approval/rejection and audit history.
- Free invoice processing with embedded PDF text, local Tesseract OCR, conservative field extraction and an optional local Ollama adapter. Failures preserve documents and permit manual review.
- Payments allocated across invoices, overpayment protection, idempotent submission and audited voiding of mistakes.
- Evidence-backed expected invoices with resolution and exemption workflows.
- Protected employee records, monthly payroll drafts, approval/payment recording, and downloadable PDF payslips.
- Private document library, supplier CSV reports, payroll totals, user administration, settings and an audit trail protected from ordinary database updates/deletes.
- Server-side pagination/filtering, responsive layouts, meaningful errors and automated workflow tests.

This is a runnable first release and an extensible foundation. It is not yet a deployed production service. The selected cloud setup uses Render Free and Supabase Free. Free OCR runs locally without an API key; local AI is optional and not installed. Cloud account credentials are intentionally absent. See [verification and remaining release checks](docs/VERIFICATION.md) before using real business data.

## Free cloud setup

Follow [the free deployment guide](docs/DEPLOYMENT.md). The included `render.yaml` and `Dockerfile.free` run the app and OCR in one free web service, with PostgreSQL and private files on Supabase Free. Free hosting sleeps and has quotas; it is a constrained pilot, not an uptime-guaranteed production service. No paid service has been purchased or configured.

## Quick local start (Windows)

Requirements: Python 3.13, Node.js 22+ and pnpm 11.19.0. A PostgreSQL/Docker installation is recommended for realistic multi-user testing; the quick preview uses SQLite strictly for development.

From this project folder:

```powershell
corepack enable
corepack prepare pnpm@11.19.0 --activate
./scripts/start.ps1 -Demo
```

Choose a demo password when prompted. Open [the local workspace](http://localhost:5173). The script creates an isolated Python environment, installs locked dependencies, migrates the development database, optionally seeds demo data, builds the frontend and starts the API, worker and preview in the background. Logs go to `.runtime/`. Stop with `./scripts/stop.ps1`.

The seeded accounts are `owner@demo.local` and `staff@demo.local`. Both use the `DEMO_PASSWORD` you supplied. The copy created during this build uses **`FamilyDemo!2026`** for those two local demonstration accounts. This is a demonstration password, never a production credential. Seeding is explicit, idempotent for an existing demo account and blocked in production. All sample invoice documents are marked as demonstrations.

## Manual setup (Windows, macOS or Linux)

```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: ./.venv/Scripts/Activate.ps1
pip install -r backend/requirements.lock
cd backend
# Copy .env.example to .env, then choose database and storage settings.
alembic upgrade head
# First real account; enter name, email and password interactively:
python -m app.bootstrap
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

For free image OCR, also run `pnpm install --frozen-lockfile` in `backend/ocr`. Scanned PDF OCR needs Poppler (`pdftoppm`) on PATH; Docker includes it. See [invoice processing](docs/PROCESSING.md).

In another terminal with the same environment activated:

```sh
cd backend
python -m app.worker
```

And for the frontend:

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Use `http://localhost:5173` so the browser origin matches the development configuration. API documentation is at `http://localhost:8000/api/docs`; it is disabled in production. `/api/health` tests the database connection. The frontend calls relative `/api` paths; Vite proxies these locally and Nginx proxies them in containers.

To create demonstration records instead of a real owner, set `DEMO_PASSWORD` to at least 12 characters and run `python -m app.seed` from `backend`. Remove the environment variable afterwards. Do not seed a production or live business database.

## PostgreSQL development with Docker

1. Copy root `.env.example` to `.env` and choose a strong URL-safe `POSTGRES_PASSWORD`.
2. Copy `backend/.env.example` to `backend/.env`.
3. Run:

```sh
docker compose up --build -d
docker compose exec api python -m app.bootstrap
```

Open `http://localhost:8080`. This runs PostgreSQL, migrations, API, worker and frontend. Database and development files use named volumes. To seed this **development** environment, add `DEMO_PASSWORD` to `backend/.env`, recreate the API/worker with `docker compose up -d`, then run `docker compose exec api python -m app.seed`. Remove the demo password afterwards and recreate the containers again. Never remove the database volume to “restart” a real business installation.

## Tests and builds

```sh
cd backend
pytest -q
alembic current
cd ../frontend
pnpm build
```

For PostgreSQL integration/concurrency tests, point `TEST_DATABASE_URL` to a dedicated disposable PostgreSQL database and run `pytest -q`. Tests create and drop randomly named schemas inside that database. Never use live database credentials. The included GitHub Actions workflow runs migrations and tests against PostgreSQL and builds the frontend.

In a restricted Windows environment, use a writable test directory: `pytest -q --basetemp=PATH_TO_NEW_WORK_DIRECTORY`. If the Vite dependency optimizer cannot inspect parent directories in that sandbox, `pnpm build` followed by `pnpm preview --port 5173` provides the built application. This fallback was used for the verified local preview.

## Documents to read

- [Environment variables](docs/ENVIRONMENT.md)
- [Cloud deployment and backups](docs/DEPLOYMENT.md)
- [Architecture and adding modules](docs/ARCHITECTURE.md)
- [OCR and AI configuration](docs/PROCESSING.md)
- [Operating guide](docs/USER_GUIDE.md)
- [Design system](docs/DESIGN_SYSTEM.md)
- [Verification record and limits](docs/VERIFICATION.md)

The project deliberately avoids inventory, sales, full accounting and statutory payroll automation until those workflows are specified. It supports MYR and one business. Payroll deductions must be entered and checked by the person responsible for payroll; no statutory compliance calculation is implied.
