# Free cloud setup for HAJJAH SITI GLOBAL

The selected setup uses **Render Free** for the application and OCR, **Supabase Free** for PostgreSQL and private files, and a **GitHub Free private repository** for source. Use the included free `onrender.com` address. No paid AI API, paid worker, subscription, domain purchase or credit is required by this configuration. No accounts have been created or services deployed from this workspace yet.

## Know the free limits

Render Free sleeps after 15 minutes without inbound traffic, and waking can take about a minute. It has 750 free instance hours per workspace per month, an ephemeral filesystem and no free persistent disk or separate worker. Render explicitly does not recommend this tier for production applications. This is therefore a constrained business pilot, without an uptime guarantee. Processing pauses while the host sleeps and resumes when the app wakes; jobs and originals are stored outside the host. Do not run artificial keep-alive traffic. [Render free service documentation](https://render.com/docs/free).

Supabase Free currently includes a 500 MB database, 1 GB file storage and 5 GB egress. Projects can pause after a week of inactivity and automatic backups are not included. Keep independent backups and check usage before adding many invoice scans. [Supabase pricing](https://supabase.com/pricing).

Choose Free in each account. Do not enable upgrades or add paid resources. If account verification requires payment or the dashboard no longer offers these free plans, stop there and reassess; do not substitute a paid plan. Ordinary internet/electricity costs and storage on equipment you already own remain outside the software.

## 1. Put the source in your own repository

Create a GitHub Free account if needed and a **private** repository, then upload the contents of this project folder so `render.yaml`, `Dockerfile.free`, `backend` and `frontend` are at repository root. The supplied source ZIP excludes local databases, private files, passwords and installed dependencies. Never upload your working `.env` or demo database. Keep your provider accounts under the business owner's control.

## 2. Create the free database and file bucket

In Supabase, create an organization on Free and one project. Choose Singapore if available and save a strong database password privately. From **Connect**, copy the **Session pooler** PostgreSQL connection string (port 5432, IPv4 compatible). This long-running API uses session pooling, not transaction pooling. Replace the URL scheme with `postgresql+psycopg://`, insert the URL-encoded password and add `?sslmode=require`. For example:

```text
postgresql+psycopg://postgres.PROJECT_REF:URL_ENCODED_PASSWORD@SESSION_POOLER_HOST:5432/postgres?sslmode=require
```

Use the host and user actually shown in your project. [Supabase connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres).

Create a **private** Storage bucket named `business-documents`. In Storage S3 settings generate server-side S3 access keys. Copy the endpoint, region, access key ID and secret into Render's secret environment fields in the next step. S3 keys have broad bucket access and must never go into browser code. The client uses path-style S3 signatures and does not send unsupported AWS encryption headers. [Supabase S3 authentication](https://supabase.com/docs/guides/storage/s3/authentication).

The application creates its tables in `hsg_operations`. Keep this schema out of Supabase's exposed Data API schemas. Do not add anonymous grants or public bucket policies. The frontend talks only to our authenticated FastAPI API; it does not use Supabase's browser SDK or public Data API.

## 3. Deploy the free application

In Render, create a Free workspace, connect the private GitHub repository and create a Blueprint using `render.yaml`. Verify the service says **Free** before creating it. The blueprint defines one Docker web service, with the frontend, API and one OCR worker in the same container. It does not create a Render database or paid worker.

Fill these environment values directly in the Render dashboard:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Supabase session-pooler URL above |
| `FRONTEND_ORIGIN` | Exact Render HTTPS address, no trailing slash; update after Render assigns the address if necessary |
| `S3_ENDPOINT_URL` | Endpoint copied from Supabase S3 settings |
| `AWS_DEFAULT_REGION` | Supabase bucket region |
| `AWS_ACCESS_KEY_ID` | Supabase S3 access key ID |
| `AWS_SECRET_ACCESS_KEY` | Supabase S3 secret |
| `INITIAL_OWNER_NAME` | Business owner's name |
| `INITIAL_OWNER_EMAIL` | Real owner email for login; email delivery is not required |
| `INITIAL_OWNER_PASSWORD` | Unique password, at least 12 characters and no more than 72 UTF-8 bytes |

Keep `FREE_ONLY=true`, `OCR_PROVIDER=local`, `EXTRACTION_PROVIDER=rules`, `INLINE_WORKER=true`, `DATABASE_SCHEMA=hsg_operations` and the other defaults in `render.yaml`. `DEMO_PASSWORD` must be absent. These secrets are entered in the provider dashboard, never in chat or source control.

At startup `python -m app.launch` runs migrations, creates the initial Boss only if the database has no users, then starts the API and durable job consumer. No sample suppliers, invoices or payroll are added. First deployment can take several minutes to build. Check `/api/health` returns `status: ok`. Set `FRONTEND_ORIGIN` to the actual address and redeploy before logging in if its initial value was a placeholder.

Sign in with the initial owner credentials, then remove `INITIAL_OWNER_PASSWORD` from Render's environment and redeploy. Existing users are preserved. Add Staff through Settings. This initial setup is designed for a dedicated new project and one application service; do not deploy two initializers concurrently against an empty database.

## 4. Verify before entering real transactions

1. Log in as Boss, confirm the HSG identity and change the password from the account page if needed.
2. Add a supplier, upload an image and scanned PDF, wait for Needs review, compare fields, choose the supplier and save corrections. Verify with human confirmation.
3. Enter a small test invoice and partial payment; confirm the balance, then void the test payment with an explanation. Payments only record bookkeeping; this app does not transfer funds.
4. Sign in as Staff and confirm payroll, financial reports, settings and other staff's invoices are inaccessible.
5. Confirm the private original is inaccessible after logout. Inspect a sample payslip and confirm the payroll foundation suits your current process.
6. Make a database and file backup, then test a restore into a separate non-live environment. Run the included PostgreSQL integration tests on a disposable database before broader use.

## Backups without a paid service

Keep backups on private storage you control. A database-only backup does not include invoice files. Install PostgreSQL client tools of the same major version as your database (or newer) on your computer. With the application's environment configured, run from `backend`:

```sh
python -m app.backup --output ../backups
```

This writes a custom-format PostgreSQL dump, every document referenced by the database, and a SHA-256 manifest into a new timestamped folder. It verifies document hashes. Pause business edits/uploads while taking a backup; the database and object service do not share a single transaction. The command does not modify business data. Back up after each business day with new records and before migrations. Keep more than one copy and periodically test restoring the dump with `pg_restore` into a separate database and re-uploading the objects under their original keys to a separate private bucket. Configure that restored app with the replacement database and bucket, then verify bills and document hashes.

Backups contain salaries and other confidential data. Protect and encrypt the destination using your operating system or existing encrypted drive. Never commit the folder or put it in a public file share. Monitor the providers' usage pages; if free limits are reached, reduce retained duplicate backup copies outside the live bucket or pause new uploads until a suitable free arrangement is available. Never delete original business documents solely to make a quota warning disappear.

## Operation and future deployment

The dashboard reflects real records. The health endpoint checks the database, not OCR/storage readiness. Failed processing leaves an accessible original and a manual-review/retry path. One local OCR task runs at a time to limit memory. Long or poor-quality scans can require manual entry on free hardware. The application remains available only subject to the free providers' availability and quotas.

For local Docker development use `docker compose up --build -d`; this consumes only your own computer resources. The separate API/worker architecture and `compose.production.yml` remain available for infrastructure you already operate. No paid infrastructure is required or provisioned by the selected Render blueprint. See [architecture](ARCHITECTURE.md) for moving these units later without changing the business model.
