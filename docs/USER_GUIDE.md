# Operating the workspace

## Start with the review queue

The owner dashboard highlights verified supplier liabilities, invoices needing review, overdue payments and expected documents that need follow-up. These figures come from records, not manually entered balances. Select an invoice or follow an alert to take action.

Staff land in Supplier bills and see their own submissions. They can upload, correct and verify their invoices. Payroll, employees, reports, supplier administration, user administration and settings are restricted to owners. Select your name at the bottom of the sidebar to change your password. Use the adjacent sign-out control to end the session.

## Suppliers

Create the supplier before verifying an invoice. Enter the contact and payment terms, then use the supplier profile to see bills, payments, original documents and outstanding balance. Terms are reference information; check the due date printed on the actual invoice when entering or reviewing it.

Deactivate a supplier when it should no longer be selected for new work. Historical bills remain linked to it. Do not rename a supplier to represent a different legal business; create a separate supplier record.

## Invoice workflow

1. Select **Upload invoice**, choose a valid PDF/JPG/PNG, then upload. The original document is stored privately.
2. The worker attempts text extraction/OCR and structured extraction. If a service is unavailable, the original stays available with a useful explanation. Enter the fields manually or retry after the service is restored.
3. Open the invoice. Compare the original on the left with supplier, number, dates, totals and line items on the right. The PDF toolbar supports zoom and page navigation; use Open full document or Download for the original file.
4. Match the supplier and correct fields. Line tax is an **amount**, not a percentage. Each line must satisfy quantity × unit price + tax = line total. All lines and taxes must reconcile to the invoice totals.
5. Save corrections before verifying. Verification applies to the saved record and records who reviewed it and when. Unverified bills do not contribute to outstanding balances.
6. A possible duplicate is a warning, not automatic rejection. An owner must compare it and provide an explanation if both records should be verified. Owners can also reject an unpaid invoice with a reason.
7. Owners can approve a verified invoice. Approval is optional for recording payment in this release; verification is required.

Use Manual invoice when entering a record without uploading a document. The system clearly identifies the absence of an original attachment. Staff ownership restrictions still apply.

## Payments and corrections

Record a payment only after it has happened. Choose the supplier, payment date, reference and method, then allocate amounts to the related verified invoices. Review the confirmation before recording. Payment amounts cannot exceed the remaining balance. One payment can cover multiple invoices from the same supplier.

The application does **not** send money. It records what happened outside the system. A partial payment reduces outstanding liability automatically; paid invoices stop appearing in outstanding queues.

If a payment was recorded incorrectly, choose Void and explain why. The original payment and allocations remain in history and no longer reduce the outstanding balance. This does not reverse an actual bank transfer. Record the correct payment separately. Supplier refunds, credit notes and exchange differences need a future accounting workflow.

Once payments are allocated, invoice financial fields are locked. An owner may correct an unpaid invoice; doing so returns it to Needs review, requiring a fresh verification. The prior values and verification remain in the audit trail.

## Expected invoices

Create an expectation only when there is evidence, such as a delivery note or supplier confirmation. If the date passes, the record is labelled Potentially missing. Follow up, then either link a verified invoice to resolve the expectation, or exempt it with a reason. This avoids false claims that an invoice was lost.

## Employees, payroll and payslips

Owner-only employee profiles store employment and payment details. List views omit bank account numbers; opening the detailed profile is audited. Update salary for future payroll periods without changing already prepared payroll snapshots.

Prepare payroll for one employee and period. The system copies current basic salary and calculates gross/net from allowances, overtime and entered deductions. Review the draft, approve it and record the payment date when paid. One record per employee per month prevents duplicate payroll.

Payslips can be downloaded from Payroll or Payslips. Draft payslips are labelled. Payroll calculation does not automatically compute Malaysian statutory deductions. The responsible operator must determine and enter applicable deductions before approval. Employee self-service is not enabled.

## Reports and audit

Filter supplier reports by invoice date and supplier; export a CSV when useful. The report combines invoices in the date range with payments allocated to those invoices as of now. It is not a historical balance-as-of report. Payroll totals use approved and paid records.

The audit trail records important changes with actor, timestamp and relevant metadata. Invoice edits include previous and new values. There is no edit or delete control for audit records.

## Users and access

Owners create users with either Staff or Business owner access. Existing sessions are revoked when a user's access changes. A user cannot demote or disable their own account; another owner must perform that action. At least one active owner must remain. Fixed role profiles can be inspected in Settings → Permissions; changing a user's assigned profile is the supported permission-management workflow.
