# Stock wastage

Staff report goods name, damage date, quantity in kg (three decimal places), damage details and 1–5 JPG/PNG photos totalling at most 15 MB. The authenticated reporter's ID and name are recorded automatically. Original submissions are immutable.

The workflow is `awaiting_decision` → `action_required` → `proof_submitted` → `completed`. Boss selects dispose, keep or other and supplies instructions. All actions require fresh photos and an explanation from the original reporter. Boss accepts the evidence or requests more evidence; old evidence is retained. A reporter cannot review their own proof. If a Boss reports damage, another Boss must review the evidence.

In-app notifications alert owners to new reports and proof, and the reporting staff member to instructions, requests for more evidence and acceptance. The bell refreshes every 30 seconds while the app is visible. Notifications are persisted for the user's next login; there are no paid email, SMS or push services.

Staff list, detail, notification and private document endpoints enforce ownership. Boss reviews all cases. Decisions and reviews use version checks and database row locks. Audit entries preserve who did what and when. Exact previously submitted evidence is blocked as new proof. Images alone cannot establish that disposal happened: staff are prompted to include the case reference and Boss must review the evidence. Image manipulation/perceptual fraud detection is not claimed.

Photos use the existing private object storage. Migration `f920_wastage` adds wastage, evidence and notification tables. Deployment runs the normal Alembic upgrade; no existing business records are removed. This module records wastage incidents and does not deduct inventory, since a stock ledger has not yet been implemented.

People is temporarily hidden using `PEOPLE_ENABLED = false` in `frontend/src/features.ts`. Employee/payroll/payslip navigation and direct frontend routes are hidden, as is the payroll report section. Existing HR data and protected APIs are retained. Set the flag to true and rebuild to restore those screens.
