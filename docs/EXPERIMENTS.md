# Experiments

Every idea is a hypothesis with a switch. We turn it off, measure, turn it on, measure. Only numbers produced by the test harness go here, with the command and commit. Use the run-ablation skill.

## Main metrics (same for every experiment)
- Automation rate: share of claims decided with no human.
- Auto approve precision: of auto approved claims, share that truly should be paid at that amount.
- Payable recall: of claims that should be paid, share that were auto approved.
- False reject rate: share of payable claims that got auto rejected. Must stay near zero.
- Calibration error (ECE).
- Human reviews per 1000 claims.
- Total cost: wrong payouts plus review cost, in SAR.
- Extraction field accuracy (for extraction experiments).

## Test sets
- synthetic_tune: generated, used for tuning weights and calibration. Never used for final numbers.
- real_extraction: ReceiptSense, SROIE, CORD samples. Extraction accuracy only.
- real_e2e: real receipt images from the public datasets, each with a synthetic claim context so the correct outcome is known. Final numbers.

## Experiment list

| ID | Idea | Switch | Hypothesis | Main metric | Result |
|---|---|---|---|---|---|
| E1 | Read the ZATCA QR first | qr_first_enabled | QR first improves accuracy on total, date and VAT number | Field accuracy | pending |
| E2 | Arithmetic checks as confidence | arithmetic_checks_enabled | Catches misread totals and lowers wrong approvals | Auto approve precision | pending |
| E3 | Council vs one judge | council_enabled | Council beats the case reviewer alone (needs Gemini key) and beats the document checker alone | Precision at the same automation rate | pending |
| E4 | Tuned weights vs equal weights | weights_tuned | Tuned weights beat equal weights | Total cost | pending |
| E5 | Disagreement sends to human | disagreement_routing_enabled | Catches wrong approvals that the average hides | Auto approve precision | pending |
| E6 | Calibration | calibration_enabled | Calibrated scores make cost-based lanes safer | ECE and total cost | pending |
| E7 | Cost-based lanes vs one fixed threshold | cost_lanes_enabled | Fewer reviews for the same precision | Reviews per 1000 | pending |
| E8 | Self-fix choice | self_fix_enabled | Members fix many low scores themselves | Reviews per 1000, self-fix success | pending |
| E9 | History member | history_member_enabled | Raises automation for trusted members and providers | Automation rate; false reject rate new vs tenured | pending |
| E11 | Reader: EasyOCR vs PaddleOCR vs Gemini free tier | reader | A vision model reads messy and Arabic receipts better than OCR plus rules | Field accuracy | pending |
| E10 | Member preview before submit | preview_enabled (simulated) | Fewer bad submissions reach the pipeline | Claims needing self-fix | pending |

E9 has a fairness check: the false reject rate for new members must not be higher than for tenured members. If it is, the history member is off until fixed.

## Results log
Add one block per run, newest at the bottom.

```
Run: E?
Date:
Commit:
Command:
Test set:
Switch off: <metrics>
Switch on: <metrics>
What it means, in one or two plain sentences:
```

```
Run: E11 part 1, EasyOCR reader alone (no PaddleOCR or Gemini comparison yet)
Date: 2026-11-24
Commit: f087ab9
Command: uv run --extra ocr reimbursement-council make-receipts --count 60 --seed 1 --out data/receipts/eval_s1
         uv run --extra ocr reimbursement-council read-accuracy data/receipts/eval_s1 --reader easyocr
Test set: 60 generated receipts (seed 1). Synthetic, not real. Layouts: clinic_arabic_first 29,
          clinic_bilingual 23, pharmacy_bilingual 8. About 70 percent carry a ZATCA QR.
          Photo damage: none 18, light 29, heavy 13.
Result, share of receipts where the field was read exactly right (QR first, then checks):
  total 0.967, subtotal 0.983, VAT amount 0.867, VAT number 0.983, treatment date 1.000,
  invoice time 0.967, provider 0.900, patient 0.550, QR found when present 0.783,
  line item service codes 0.622.
By damage:
  none (18):  every field 1.000, item codes 1.000
  light (29): total 1.000, VAT amount 1.000, patient 0.517, QR 0.759, item codes 0.701
  heavy (13): total 0.846, VAT amount 0.385, patient 0.000, QR 0.538, item codes 0.000
Time: 604 seconds for 60 receipts on a laptop CPU (cached afterwards).
What it means: on a clean photo the reader gets everything right. Amounts survive light damage
because the arithmetic checks and the QR back them up. Names and line items are the weak spot
on damaged photos, and heavy damage breaks item reading, so those claims must go to self-fix or
a human, not auto approve.
```
