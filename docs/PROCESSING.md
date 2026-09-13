# Free invoice OCR and extraction

The default pipeline is private upload → durable job → embedded PDF text or local Tesseract OCR → conservative field rules → validation → human review. It requires no paid API key. `FREE_ONLY=true` blocks the external OCR and AI adapters retained as extension points.

## What works by default

- PDF text extraction with pypdf, including mixed documents where scanned pages need OCR.
- Image and scanned PDF OCR using Tesseract. Linux containers include English and Malay language data plus Poppler for PDF rendering.
- Suggestions for common invoice-number labels, day/month/year or ISO dates, MYR subtotal, tax and total labels.
- A reviewable copy of the OCR text. Missing fields remain blank/zero and must be corrected. Supplier matching and line items are human tasks in the default rules mode. The reviewer can enter product grades, fractional weights and units such as kg, g, bag or carton.
- All extracted records enter Needs review. No confidence percentages are invented. Verification checks the supplier, dates and financial arithmetic. Explicit unsupported currency codes fail into manual review rather than silently converting money.

This default is **OCR plus rules, not an AI model**. Varied supplier layouts, handwriting, tilted photos, multi-column totals and multilingual product descriptions can need corrections. Always compare the original. The system does not manufacture line items when it cannot extract them reliably.

## Windows and local development

The Windows startup script installs the small Node OCR package from `backend/ocr` using pnpm. If native Tesseract is not available, Tesseract.js runs locally through Node. Its first use downloads public language data and caches it in `.ocr-cache`; invoice images stay on the host. The first page therefore takes longer. Node 22+ must be on PATH.

For manual setup:

```sh
cd backend/ocr
pnpm install --frozen-lockfile
```

Scanned PDFs additionally require `pdftoppm` from Poppler on PATH. Native Tesseract and Poppler are bundled in both Docker images. `OCR_LANGUAGES=eng` works with the default local setup; choose `eng+msa` when the Malay data is installed. Keep the cache directory private and writable by the worker. Run `python -m app.worker` alongside the local API, or set `INLINE_WORKER=true` for one combined process. Do not run both consumers against the SQLite preview.

## Optional free local AI

An Ollama adapter is included for an AI model running on hardware you already own. No model has been installed or AI inference verified in this workspace. Model download size, license and hardware requirements depend on your chosen model. This is optional; the cloud free host is sized for OCR/rules, not a large language model.

After installing a suitable local model, configure:

```text
EXTRACTION_PROVIDER=ollama
EXTRACTION_ENDPOINT=http://127.0.0.1:11434/api/chat
EXTRACTION_MODEL=YOUR_INSTALLED_LOCAL_MODEL
FREE_ONLY=true
```

The adapter permits only loopback or explicitly local container hostnames. It submits OCR text with the input schema, validates the result, discards model-supplied supplier IDs and keeps human review mandatory. It has no tools or authority to approve invoices or make payments. Do not expose Ollama publicly or use a hosted paid endpoint. The selected free cloud configuration remains rules-based; accessing your local model would require a separately designed private worker connection and your computer to be running.

No unpaid external AI provider was selected for business invoices. This avoids silently sending confidential supplier records to an unrelated AI service.

## Failure and restart behavior

Jobs are stored in the relational database. OCR reads private files, limits page rendering size and processes one invoice at a time. An image has a 75-second OCR timeout; PDF processing checks an overall time budget between pages. Failures retain the original and permit manual entry or retry. The worker uses a ten-minute lease and rejects stale completions. On free hosting, jobs can pause when the host sleeps and resume on wake.

Uploads accept PDF/JPEG/PNG content up to 15 MB, up to 50 PDF pages and 30 million image pixels. Password-protected and detectable active PDFs are rejected. Baseline file checks are not an antivirus engine. There is an adapter boundary for adding quarantine scanning if later required.
