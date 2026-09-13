# Environment variables

Backend settings load from the working directory's `.env`; process environment overrides the file. Cloud secrets belong in the provider dashboard. No secret is bundled in the frontend.

| Variable | Purpose / default |
|---|---|
| `ENVIRONMENT` | `development`; `production` requires PostgreSQL, HTTPS, S3 and no demo password |
| `DATABASE_URL` | SQLite only for preview; production `postgresql+psycopg://...?...sslmode=require` (use `?sslmode=require` as the first query parameter) |
| `DATABASE_SCHEMA` | Blank locally; `hsg_operations` for the Supabase deployment, kept out of exposed Data API schemas |
| `FRONTEND_ORIGIN` | Exact allowed browser origin with no trailing slash; HTTPS in production |
| `STORAGE_BACKEND` | `local` for development; `s3` for private cloud storage |
| `STORAGE_PATH` | `./private-files`, never a public frontend directory |
| `S3_BUCKET` | Private bucket name, `business-documents` for the selected setup |
| `S3_ENDPOINT_URL` | Endpoint copied from Supabase S3 settings |
| `AWS_DEFAULT_REGION` | Storage region; these AWS-named variables also configure compatible Supabase storage |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Server-only S3 credentials; not Supabase browser/anon keys |
| `S3_SERVER_SIDE_ENCRYPTION` | Leave blank for Supabase; optional header for storage providers that support it |
| `COMPANY_NAME`, `BUSINESS_TYPE` | `HAJJAH SITI GLOBAL`, `Dried seafood` |
| `SESSION_HOURS` | 12 |
| `UPLOAD_LIMIT_MB` | 15; align any ingress limit if changing this |
| `FREE_ONLY` | **true**; keep enabled to block paid/external extraction adapters |
| `OCR_PROVIDER` | **local** |
| `OCR_LANGUAGES` | `eng` locally; `eng+msa` in Docker free deployment |
| `OCR_CACHE_PATH` | `./.ocr-cache`; private, writable temporary/cache directory |
| `TESSERACT_COMMAND` | `tesseract`; native executable or path; Node fallback when absent |
| `EXTRACTION_PROVIDER` | **rules**; optional `ollama` for a locally installed AI model |
| `EXTRACTION_ENDPOINT`, `EXTRACTION_MODEL` | Only needed for optional local Ollama; blank in selected cloud setup |
| `INLINE_WORKER` | false locally with a separate worker; true in the free single-container service |
| `FRONTEND_DIST` | Blank with separate frontend; `/app/frontend-dist` in Dockerfile.free |
| `PORT` | Hosting port, defaults to 10000 for `app.launch` |
| `INITIAL_OWNER_NAME`, `INITIAL_OWNER_EMAIL`, `INITIAL_OWNER_PASSWORD` | One-time cloud bootstrap only; remove password after first successful login |
| `DEMO_PASSWORD` | Explicit local seed only, at least 12 characters; absent in production |
| `API_PROXY_TARGET` | Frontend development proxy, default `http://127.0.0.1:8000` |
| `TEST_DATABASE_URL` | Disposable PostgreSQL test database only; never live credentials |
| `POSTGRES_PASSWORD` | Root local Compose `.env`, for your own development database |

Legacy `OCR_ENDPOINT`, `OCR_API_KEY` and `EXTRACTION_API_KEY` are unused in the selected free setup. Leave them blank. External provider code is guarded by FREE_ONLY and no paid service is contacted by the default pipeline.

Authentication uses opaque revocable sessions, so no JWT signing secret is required. Passwords use bcrypt, at least 12 characters, maximum 72 UTF-8 bytes. Every user can change their own password from their account page. The owner assigns roles and supplies initial staff passwords through a private channel.

Never commit `.env`, `.env.production`, local databases, backups, OCR cache or invoice files. URL-encode special characters in database passwords. All browser API calls are relative `/api` requests; no hosting URL or API credential is hard-coded in the frontend.
