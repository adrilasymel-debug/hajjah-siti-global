# Verification record · 14 September 2026

## Supplier-entry release check

The current source passes **27 backend tests**, with one PostgreSQL concurrency test skipped. The frontend production build passes. The running updated application is available at `http://localhost:8080`; the older preview on port 5173 was not interrupted.

Browser checks passed across every major page, with no JavaScript errors or mobile overflow. A Staff browser session created an invoice with a new supplier name, entered another new supplier while reviewing it, saved, reloaded and confirmed both suppliers were reusable. The unsaved-change verification guard remained active. QA invoices were rejected and QA suppliers deactivated afterwards; no real payment or verification was made. The initial toast-based test timed out despite a successful save; the final test waits for the save response and verifies persisted data after reload.

Names match existing suppliers case-insensitively before creating a new record. Staff can add a supplier through an authorized invoice save while full supplier administration remains owner-only. Failed/stale/unauthorized edits do not create suppliers. PostgreSQL serializes simultaneous inline creation for the same name. No migration is needed for this change.

This records what was exercised in the Windows workspace. The application runs locally; the cloud configuration has not yet been deployed into the business owner's accounts.

## Automated checks

- **23 tests passed, 1 PostgreSQL concurrency test skipped** in the final full backend run. Two upstream test-client deprecation warnings remain.
- Coverage includes authentication/logout/CSRF, roles and ownership, suppliers, verification, duplicates, financial arithmetic, payment allocation/overpayment/voiding, payroll, private files, upload validation and audit events.
- Migration tests preserve existing payment records and exercise append-only audit protection. The development database is at revision `e810_unit`.
- Free-mode tests block external OCR/AI calls, preserve unknown fields, reject explicit unsupported currency and require human review.
- Bootstrap tests create one hashed-password Boss account and ensure subsequent starts do not reset it.
- Backup tests verify document hashes, detect corruption and keep credentials out of command arguments. The dump subprocess is substituted; a real cloud backup/restore remains to be tested.
- Production frontend build and TypeScript checks pass.

## Real OCR and startup

A synthetic dried-seafood invoice image and a scanned PDF were uploaded through the authenticated API into a separate empty test database. Actual local Tesseract.js OCR and field extraction recovered the invoice number, dates and RM 750 total. The inline worker saved Needs review records, with neither automatically verified. This was real OCR, not a substituted provider response.

The combined `app.launch` path migrated an empty development database, created the first owner, served the React frontend/API together, passed health checks, preserved API 404 responses and consumed both OCR jobs. Docker was unavailable here, so the Linux container build and native Linux Tesseract still need deployment verification.

The existing demo now has HAJJAH SITI GLOBAL branding and free OCR. Windows denied termination of earlier demo workers. Current records were therefore copied using SQLite's backup API into a separate development database; the updated API/worker use that copy. The old database and original files were retained. Previously untouched failed uploads were retried, and the updated preview finished with **zero failed or queued invoices**. This is development recovery, not a production migration.

## Browser and visual checks

Headless Edge with Playwright exercised the dashboard and all major modules: bills, suppliers, payments, outstanding, expected invoices, employees, payroll, payslips, documents, reports, audit and settings. No JavaScript errors were captured. Desktop and 390-pixel mobile screenshots were inspected; no horizontal page overflow was detected.

Interaction checks covered Staff navigation restrictions, forbidden-route redirect, PDF canvas rendering/zoom, unsaved-correction verification guard, logout, supplier-payment allocation fields, employee editing and user-creation dialogs. Dialogs were cancelled before submitting business changes. Shared controls now have explicit accessible names. A demonstration payslip was rendered and visually inspected during the build.

The Windows start/stop scripts parse successfully. An attempted start while the API port was occupied correctly refused a duplicate launch. The full installation/start/stop cycle has not been repeated after adding that guard.

## Remaining release boundaries

- The owner must create free Render/Supabase/GitHub accounts and enter secrets directly in provider dashboards. No paid service or AI API was configured; there is no live cloud URL yet.
- PostgreSQL concurrency and private-schema behavior need testing on a disposable PostgreSQL database. The included GitHub Actions workflow supplies PostgreSQL for integration tests.
- Validate private storage, HTTPS sessions, wake/retry behavior and resource usage in the actual free deployment. Free hosting sleeps and has quotas; it does not guarantee production uptime.
- OCR accuracy across real supplier layouts is not established. Default extraction uses rules; supplier matching and line items remain human tasks. Optional local Ollama is integrated, but no model was installed or inference tested.
- Payroll has no statutory calculations. Reports are operational summaries. Credit notes, inventory, sales, employee self-service and a custom permission designer remain future modules.
- Perform a real database/object backup and restore before relying on the hosted pilot for the only copy of business records.

See [deployment](DEPLOYMENT.md), [processing](PROCESSING.md) and [architecture](ARCHITECTURE.md) for setup and extension points.
