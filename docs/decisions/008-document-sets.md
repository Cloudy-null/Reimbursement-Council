# 008: A claim is a set of documents, checked before it is sent

Date: 2026-11-24
Status: Accepted by the owner on 2026-11-24 (design in docs/superpowers/specs/2026-11-24-document-set-design.md, sections 5 and 9). Built in tasks 1 to 15 of docs/superpowers/plans/2026-11-24-document-set.md.

## Context
The brief asks for a claim journey with no manual data entry: the member uploads documents, the system reads them, finds what is missing or does not match, and says exactly what to fix before the claim is sent. Until now the website took one photo, treated it as a receipt and decided at once. Other documents were stored but never read.

## Options
- Document type: keyword match on the text and the QR the reader already finds; the member picks every type; a trained classifier.
- Claim type (benefit category): worked out from the services on the bill; the member picks it first.
- Patient check: each document against the patient's registered names on the account; document against document.
- Mixed problems (something the member can fix and something only a person can settle): ask the member first; send it all to a person.
- When the claim is checked: after it is sent (as before); on a check step before it is sent.

## Choice
- Types come from keywords in Arabic and English plus the ZATCA QR. The member sees the type and can change it.
- The category comes from the price list categories of the services read. The member can change it.
- The documents each category needs are in config/documents.yaml (made-up values until Bupa's process material arrives).
- The patient name on each document is compared with the account, in the same script. Treatment dates are compared across documents (0 days tolerance). The provider is compared only between a medical report and an outpatient or dental bill.
- Lane order (spec 6.4): a failed hard rule rejects; then everything the member can fix is asked (missing document, mismatch, clearer photo) while retries are left; then a person sees what only a person can settle (contradicting edit, possible duplicate, a field still wrong after asking once).
- Every document is read once at upload, the member checks and corrects on a check step, and the pipeline judges exactly that stored reading.
- A member edit backed by the QR, another document or the arithmetic needs no person. An edit with no evidence on a money or hard rule field first asks for a clearer photo once.

## Trade-off
- Keyword types fail on documents with no title words; those read as "other" and the member is asked. A classifier could do better but there is no labeled data.
- Asking the member first is slower for a claim that will reach a person anyway, but most such claims never need the person once the member fixes them.
- Checks before sending add a step for the member, but missing documents never become rejections, and the reviewer gets read and typed values side by side.
- The required documents per category are guesses until the real process material arrives, so the harness numbers for missing documents measure our rules, not Bupa's.
- Measured by E12 (cross_checks_enabled off and on) and the document metrics in docs/EXPERIMENTS.md.
