# Reimbursement Council: project summary

Solve for Bupa hackathon, November 2026. Brief: "From Submission to Approval: A Zero-Friction
Reimbursement Experience". Every number below comes from our test harness at one commit
(ac2a7e4); the command for each is in docs/pitch/numbers.md. No Bupa data was used.

## The problem

When a member pays a clinic or pharmacy out of pocket, they claim the money back in the app. Today
they upload documents and then type again what the documents already say: service, date, amounts.
A typo, a missing prescription or a report for the wrong day often leads to a rejection or a
request for more information days later. On the other side, a claims team opens every document,
checks it against what was typed, finds the gaps, and keys the data into the claims system. That
work grows with every claim.

## The key insight

Most of the delay comes from finding problems after the claim is sent. If the system reads the
documents and checks them while the member is still in the app, the member can fix the problem in
one minute, and a person only sees the claims that really need judgement. It must also say "I am
not sure" honestly: a wrong automatic payment costs more than a short question to the member.

## The solution

1. **Upload, no typing.** The member adds photos, scans or PDFs. Each document is read on our own
   computer by a local vision AI model (qwen3-vl, Arabic and English) and by OCR at the same
   time. The ZATCA QR code is the truth when there is one. The model only reads: every value it
   returns must be found on the document or in the QR code, or it is dropped
   (docs/MODEL_SAFETY.md). When the two readers disagree, the member is asked.
2. **Check before sending.** The member sees what was read. The app names any missing document
   ("Please add a prescription") and any mismatch (another patient's name on the report, another
   date). The member can correct a value; a change the QR code does not support goes to a person
   with both values side by side.
3. **Decide with care.** Hard rules (late, not covered, duplicate) can reject. A council of checks
   (document quality, coverage, price, history) scores the rest. The claim goes to one of four
   lanes: approved, asked to fix one thing, a person, or rejected only on a confident rule.
4. **Hand over clean data.** Every decided claim exports as JSON that follows a published schema,
   with money in whole halalas, a source and confidence for every value, and a flag that says
   whether it is ready for automatic processing (docs/INTEGRATION.md).
5. **Built for every member.** Arabic and English on every screen, a consent step before anything
   is read, no personal data in logs, and text that meets WCAG AA contrast.

## Expected impact (measured on synthetic, real-derived and public data)

- **A real claim, predicted before submit.** On one real Bupa optical claim (used with the
  member's consent), our check page told the member to expect 450 SAR before sending, because the
  frame sub-limit was nearly used up. Bupa paid 450 SAR. (The sub-limit usage came from Bupa's
  answer; in production it comes from Bupa's records.)
- **Safe automation.** Every automatic approval was right (precision 1.0) with no false rejects in
  every synthetic run but one: with the arithmetic checks off, wrong approvals appear (precision
  0.9545). Across 150 damaged photos (ten kinds of damage, three strengths) there was no wrong
  approval: claims went to the member for a retake or to a person.
- **Better reading.** The local model with OCR read the right total on 0.6167 of real receipts,
  against 0.3333 with OCR alone, and half of the synthetic claims are decided with no person
  (0.5, against 0.35 with OCR alone).
- **Members fix it first.** With self-fix, reviews fall from 483.3 to 183.3 per 1,000 claims, and
  6 of 8 claims the members fixed were then paid right with no person.
- **Fast enough.** About 8 seconds per claim through the website for a new photo.
- **Data the claims system can use.** Every export is valid JSON against the schema, with the
  sub-limit, member share, VAT and the source of each rule.

## Feasibility

- **It runs today.** A working website (not a mockup) on one PC with a gaming GPU: reading,
  checking, deciding, adding a member, the reviewer card and the export. iPhone photos (HEIC),
  scans and PDFs are taken. A browser test runs the whole demo path with the
  real reader and passes.
- **Offline and private.** No document leaves the computer: the AI model runs on our own PC
  and refuses any server that is not on it. There is no paid service.
- **The AI is checked, not trusted.** An AI case reviewer gives one opinion per claim but can
  only send a claim to a person, never approve one. Its prompt was improved on one set of claims
  and then tested once on a held-out set it had never seen: 0.95 against a 0.90 limit, so it is
  on. A health check benches it automatically when it gets worse.
- **Honest about limits.** On real scanned receipts (SROIE, from Malaysia, with no QR code) the
  reader gets the total on 0.6167, the date on 0.6 and the shop name on 0.5167. Those receipts
  are shop receipts, not medical ones, so on them the system asks the member instead of deciding.
  Saudi receipts carry a ZATCA QR code, which we read first. Rules from Bupa's own claim FAQ
  (eye test, tooth number, proof of payment, valid tax invoice, VAT not covered, member share
  cap, sub-limits, translation) are built in; more real Saudi claims are the next step.
- **Built to change.** Every threshold, weight and rule lives in configuration files, and every
  idea has an on and off switch measured by the harness, so Bupa's own rules and data can be
  plugged in and measured the same way.
