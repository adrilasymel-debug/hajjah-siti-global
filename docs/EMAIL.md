# Free email notifications (Brevo)

Use Brevo's Free plan, currently 300 emails per day. Do not enable billing, purchase credits or choose a paid plan. The integration uses HTTPS, compatible with free Render hosting's SMTP restrictions.

1. Create a free account at https://www.brevo.com/ and complete account verification / transactional sending activation.
2. Add and verify the sender email address. Follow Brevo's sender/domain authentication requirements; use a business domain if already available. Do not buy a domain just for this setup without deciding to do so.
3. Generate an API key under SMTP & API → API keys (not an SMTP key).
4. In Render Environment, set `BREVO_API_KEY` to the secret key, `EMAIL_FROM` to the verified sender address, `EMAIL_FREE_TIER_CONFIRMED=true`, and `EMAIL_ENABLED=true`. Keep `FRONTEND_ORIGIN` set to the real HTTPS website URL. Save and deploy.
5. Each user's account email is their notification destination. Check Boss and Staff email addresses before enabling. Existing events are not backfilled.
6. Submit a new invoice or wastage report. Check Settings → Email notifications and the recipient inbox. Provider acceptance is not proof of inbox delivery: inspect Brevo transactional logs for bounces/spam issues.

Boss receives new invoice submissions, invoice verification, new wastage reports and submitted proof. Reporting staff receive invoice extraction success/failure, invoice approval/rejection, wastage instructions, requests for more proof and case completion. Emails contain fixed short descriptions and authenticated record links; no photos, financial amounts or private remarks are attached.

The outbox is committed in the same database transaction as the business event. Delivery runs separately and retries network/server failures up to five times. Quota responses wait an hour before retrying without buying credits. Owners can see failed deliveries and retry them after fixing provider configuration. Disabled/ineligible users are skipped at send time. A timeout after provider acceptance or a worker crash may produce duplicate email on retry; delivery is not exactly once.

Free Render services sleep when inactive, so notifications are not guaranteed immediate. Pending messages are retained and processed when the service wakes. Daily quota is shared with other email sent through the same Brevo account. `EMAIL_ENABLED=false` stops sending and new queue entries; pending entries remain for when it is enabled again.

Migration: normal `alembic upgrade head` adds `email_deliveries`. No existing records are deleted. No additional package is required (uses existing httpx).

Sources: https://help.brevo.com/hc/en-us/articles/208580669-FAQs-What-are-the-limits-of-the-Free-plan ; https://developers.brevo.com/docs/send-a-transactional-email ; https://render.com/docs/free
