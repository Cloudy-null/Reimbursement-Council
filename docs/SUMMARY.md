# Reimbursement Council: project summary

Solve for Bupa hackathon, November 2026. Brief: "From Submission to Approval: A Zero-Friction
Reimbursement Experience". Every number below comes from our test harness; the command and
commit for each are in docs/pitch/numbers.md. No Bupa data was used.

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
   computer (the ZATCA QR code first, then OCR in Arabic and English), and its type is found:
   invoice, receipt, prescription or medical report.
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

## Expected impact (measured on synthetic and public data)

- **Safe automation.** In every synthetic run, each automatic approval was right (precision 1.0)
  and no payable claim was rejected. On 50 real receipt scans the system made no wrong approval
  and no wrong rejection.
- **Fewer claims for the claims team.** When members fix what they are asked, 10 of 60 synthetic
  claims reach a person, against 37 of 60 when every problem goes to a person. 5 of the 8 claims
  the members fixed were then paid right with no person at all.
- **Mismatches caught before payment.** The cross-document checks caught every patient or date
  mismatch we put in (3 of 3 and 7 of 7), and in each set stopped one wrong automatic approval.
- **Data the claims system can use.** All 180 synthetic claims exported as valid JSON against the
  schema.

## Feasibility

- **It runs today.** A working website (not a mockup) on a normal laptop: reading, checking,
  deciding, the reviewer card and the export. A browser test runs the whole demo path with the
  real reader and passes.
- **Offline and private.** No document leaves the computer; there is no paid service.
- **Honest about limits.** On real scanned receipts (SROIE, from Malaysia, with no QR code) the
  reader gets the date on about half and the total and shop name on about a third. So on real
  documents it mostly asks the member to confirm, which is safe but not yet fast. Saudi receipts
  carry a ZATCA QR code, which we read first and which was exact on our synthetic receipts; real
  Saudi receipts and Bupa's own document rules (week 2 material) are the next step.
- **Built to change.** Every threshold, weight and rule lives in configuration files, and every
  idea has an on and off switch measured by the harness, so Bupa's own rules and data can be
  plugged in and measured the same way.
