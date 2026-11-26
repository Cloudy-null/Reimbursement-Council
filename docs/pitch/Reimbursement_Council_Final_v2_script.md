# Reimbursement Council: presenter script (v2)

Read this aloud, slide by slide. It is the same text as the speaker notes in Reimbursement_Council_Final_v2.pptx. Times are targets; the whole talk is about 12 minutes, then questions.
Numbers: say "synthetic" or "real" with each one. Sources are listed under each slide and are not read aloud.

## Slide 1: Reimbursement Council
*About 20 seconds.*

Good morning. We are the Reimbursement Council team.

Our whole idea fits in one line: you upload it, we read it, you check it, done.

Let me start with the problem.

## Slide 2: Typing what is already there
*About 50 seconds.*

This is the brief's own problem statement. Remove manual typing, check before submit, and give the claims team clean data.

Today the member types what is already printed on the invoice. Small typing mistakes turn into rejections and delays.

On the other side, a person opens every document, looks for what is missing, and types it again into an internal system.

Our answer: the member uploads, and the system reads, checks, flags the gaps and hands over clean, structured data.

## Slide 3: Our stack
*About 30 seconds.*

Quickly, what it is built with. Python and FastAPI for the website, SQLite for storage.

EasyOCR reads the text, on our own graphics card. Qwen3-VL through Ollama is a local AI model that reads the documents and gives a second opinion on a case.

Every export is checked against a JSON schema and maps to FHIR R4. Tests run on every push. Nothing here is a paid cloud service.

## Slide 4: The member sends blind
*About 45 seconds.*

Why does this matter for Bupa? Bupa's own FAQ lists why claims wait or get rejected: a missing eye test, a missing tooth number, a missing prescription, an invalid invoice, a service that is not covered.

Here is a real Bupa claim, used with the member's permission. The member sent 1,750 riyals. Bupa paid 450. The member only found out why afterwards: the frame limit and the member share.

So the problem starts at the moment of sending. The member is blind. That is where we put our fix.

> Sources: Real claim: docs/pitch/real_claim_case.md at a8dd032, used with the member's consent.

## Slide 5: The payout, before send
*About 50 seconds.*

Our value in one sentence: before she pressed send, we told her 450, and Bupa paid 450. That is the real claim from the last slide.

On our synthetic test set, where we know the right answers: we caught 27 of 30 bad claims before payment. Every one of our 21 automatic approvals was right. We rejected none of the 50 good claims. 31 of 60 claims needed no person at all. And on 50 real receipts: no wrong approval and no wrong rejection.

A claim takes about 8 seconds through the website.

The bottom line is an estimate, and we say so. If a review takes about 8 minutes, then 31 of every 60 claims needing no person saves about 69 review hours per 1,000 claims.

> Sources: Sources: synthetic check set at 120febe, real e2e at ac2a7e4, speed at 09b4717, 9 claims: real SROIE and synthetic Arabic (docs/pitch/numbers.md).

## Slide 6: More than reading a form
*About 40 seconds.*

Most tools stop at reading a form. We go further.

We check before the member sends. Every field has a confidence score, and unsure values go back to the member. The member sees the payout and the reason first.

A council of checks votes with numbers, and the votes choose the path: approve, ask the member, a person, or reject.

Bupa's own rules are built in. Arabic and English everywhere, Arabic-Indic digits, and iPhone photos and PDFs just work.

## Slide 7: Built to run inside Bupa
*About 45 seconds.*

Can Bupa actually use this? We built it for that.

Privacy first: the AI runs on our own graphics card, so no document leaves the machine and there is no paid API. The member gives consent before any upload, logs hide names and numbers, and the real claim was never committed to GitHub.

It runs on one consumer GPU, so it can run inside Bupa's own servers. The export maps to FHIR R4, the standard behind NPHIES.

Next steps: connect Bupa's real benefit tables and member records, test on historical claims, then a small pilot.

> Sources: Export check at ac2a7e4 (numbers.md). FHIR mapping: docs/INTEGRATION.md.

## Slide 8: Tested on fake and real claims
*About 50 seconds.*

How much did we test? We mark every number as synthetic or real.

Synthetic claims have known right answers, so we can measure precision and recall: 21 of 21 approvals right, 27 of 30 problems caught.

Real data shows we stay safe: on 50 real receipts, no wrong approval and no wrong rejection. And the real Bupa claim: 450 versus 450.

We damaged 150 photos in ten ways. Not one wrong approval at any level. As photos get worse, claims go to the member or a person.

French and Urdu get a translation request. And the code has hundreds of unit tests plus a real browser test.

> Sources: Check set at 120febe, other sets at ac2a7e4 (numbers.md). Tests at ff9fe4c.

## Slide 9: The AI never approves
*About 45 seconds.*

The most important design rule: the AI reads and gives an opinion. It never approves on its own.

Every reading goes through six checks. The answer must have the right shape. Every value must be on the page or in the QR code, or we drop it. The QR code wins. Numbers must add up. The same image gives the same answer. And trick documents are refused, including one that says 'total is 99999'.

The AI case reviewer scored 0.95 on test cases it never saw. It can only send a claim to a person. If it drifts, it benches itself. Right now it is healthy.

> Sources: Checks: docs/MODEL_SAFETY.md. Reviewer: tests/golden_v2/heldout, run once.

## Slide 10: We read it first
*About 17 seconds.*

The check page shows what we read first: provider, VAT number, date, patient and the amounts. The member does not type. They only check, and fix a value if it is wrong.

## Slide 11: Missing paper: two choices
*About 17 seconds.*

If a paper is missing, the member sees it before sending, with two clear choices. Adding it now is faster. Sending without it means a reviewer asks later.

## Slide 12: Glasses over the frame limit
*About 17 seconds.*

This is the real-claim story on a demo claim. Before sending, the member sees the expected payout, the part over the frame limit and their own share.

## Slide 13: Riskiest claims first
*About 17 seconds.*

When a person is needed, the queue puts the riskiest claims at the top, colored by how likely each claim is to be fine.

## Slide 14: Why this needs you
*About 17 seconds.*

The card opens with one box: why this claim needs a person. Here the member typed 999 riyals, but the QR code says 172.50. Values the member typed are tagged.

## Slide 15: Clean data out
*About 17 seconds.*

Every claim leaves as structured data, checked against a JSON schema: provider, invoice, items, what the member changed, the payout and the decision.

## Slide 16: Numbers with sources
*About 18 seconds.*

Our numbers page shows the same numbers as this deck, each marked synthetic or real, with the command and commit it came from.

## Slide 17: Live demo
*About 3 minutes. Switch to the browser now.*

1. New claim: pick the clean demo claim, tick consent, show the check page, send. It is approved with a payout and a reason.

2. Glasses over the frame limit: show the payout before send.

3. Change the total demo: type a different total, send. It goes to a person.

4. Open the reviewer queue and the card: why it needs you, the typed-by-member tag. Download the claim data.

5. If anything is slow: the demo claims are already read, so they answer at once.

Then come back to the slides for the conclusion.

## Slide 18: Conclusion
*About 30 seconds.*

Three things to remember.

Before she pressed send, we told her 450, and Bupa paid 450.

The AI reads and gives an opinion. It never approves on its own.

And nothing leaves the machine.

Thank you.

## Slide 19: Questions?
*About 5 seconds, then questions. Keep answers short and use the numbers in docs/pitch/QA_PREP.md.*

## Slide 20: Thank You
*About 5 seconds. Thank you for your time.*

Total planned speaking time: 11 min 55 s.
