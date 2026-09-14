# Gemini cloud invoice extraction

Set these Render environment variables, then save and deploy:

- `EXTRACTION_PROVIDER=gemini`
- `OCR_PROVIDER=gemini` (the worker sends the original directly to Gemini)
- `GEMINI_MODEL=gemini-2.5-flash`
- `GEMINI_API_KEY`: private Google AI Studio key, server only
- `GEMINI_FREE_TIER_CONFIRMED=true`: set only for a Free-tier project with billing disabled
- Keep `FREE_ONLY=true`.

The application cannot inspect billing through an API key. The Google project must remain on the Free tier with billing disabled to prevent charges. Quota failures stop processing; there is no paid or local fallback and no automatic quota retry loop. Retry from invoice review when quota is available. Originals stay in private object storage.

PDF, PNG and JPEG files up to 14 MB are sent inline to Google's cloud API. Larger valid uploads remain available for manual review. Gemini reads scanned PDFs and images without local OCR. Suggestions never verify invoices or create suppliers automatically. Confirm the suggested supplier using the existing supplier picker.

Google's free-tier terms permit use of submitted content to improve products. Consider this when sending supplier documents. See https://ai.google.dev/gemini-api/terms and https://ai.google.dev/gemini-api/docs/pricing.

Staff use My invoices to upload, correct and verify their own submissions. They can view their own original documents in invoice review. The general Documents library is owner-only, enforced by the API as well as navigation.
