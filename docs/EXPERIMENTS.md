# Experiments

Every idea is a hypothesis with a switch. We turn it off, measure, turn it on, measure. Only numbers produced by the test harness go here, with the command and commit. Use the run-ablation skill.

## Main metrics (same for every experiment)
- Automation rate: share of claims decided with no human.
- Auto approve precision: of auto approved claims, share that truly should be paid at that amount.
- Payable recall: of claims that should be paid, share that were auto approved.
- False reject rate: share of payable claims that got auto rejected. Must stay near zero.
- Calibration error (ECE), on claims no hard rule rejected (decision 007).
- Human reviews per 1000 claims.
- Total cost: wrong payouts plus review cost, in SAR. A false reject counts as the payout that should have been made (decision 007).
- Heavy damage lanes: for claims whose photo has heavy or unreadable damage, the share that went to self_fix, auto_approve, auto_reject and human_review, and the count of wrong auto approves among them. Wrong auto approves on unreadable photos is the number we care about most; it should be 0.
- Extraction field accuracy (for extraction experiments).
- Document metrics (synthetic/document_metrics.py, in every run-set output since Task 11). Each is a share with its group size next to it (name_count), so a 0.0 from an empty group is not a bad result.
  - document_kind_accuracy: of all documents, share whose found type equals the true type (strict: a billing document read as receipt when it is an invoice counts as wrong).
  - missing_document_recall: of the required groups that are truly missing, share the pipeline flagged.
  - missing_document_precision: of the groups the pipeline flagged as missing, share that are truly missing.
  - cross_check_catch_rate: of claims with a patient or date mismatch put in on purpose, share where a cross check failed.
  - cross_check_false_alarm_rate: of the other claims, share where a cross check failed anyway.
  - expected_lane_match: of claims whose document defect decides the lane (missing document, mismatch, contradicting edit), share that went to that lane.

## Test sets
- synthetic_tune: generated, used for tuning weights and calibration. Never used for final numbers.
- real_extraction: ReceiptSense, SROIE, CORD samples. Extraction accuracy only.
- real_e2e: real receipt images from the public datasets, each with a synthetic claim context so the correct outcome is known. Final numbers.

## Experiment list

| ID | Idea | Switch | Hypothesis | Main metric | Result |
|---|---|---|---|---|---|
| E1 | Read the ZATCA QR first | qr_first_enabled | QR first improves accuracy on total, date and VAT number | Field accuracy | pending |
| E2 | Arithmetic checks as confidence | arithmetic_checks_enabled | Catches misread totals and lowers wrong approvals | Auto approve precision | Off: correct rejects 0.70 to 0.40 (3 excluded-service claims ask the member instead), automation 0.383 to 0.333; precision 1.0 both (synthetic check, 60) |
| E3 | Council vs one judge | council_enabled | Council beats the case reviewer alone (needs Gemini key) and beats the document checker alone | Precision at the same automation rate | Document checker alone vs full council: 1 more auto approve (an overpriced claim, paid right at the network price), reviews 133 to 117 per 1000; precision 1.0 both (synthetic check, 60). Not the hypothesis; one claim |
| E4 | Tuned weights vs equal weights | weights_tuned | Tuned weights beat equal weights | Total cost | pending |
| E5 | Disagreement sends to human | disagreement_routing_enabled | Catches wrong approvals that the average hides | Auto approve precision | Off: the same one overpriced claim is auto approved instead of reviewed, reviews 133 to 117 per 1000; precision 1.0 both (synthetic check, 60) |
| E6 | Calibration | calibration_enabled | Calibrated scores make cost-based lanes safer | ECE and total cost | ECE 0.155 to 0.051, cost 175 to 125 SAR, precision 1.0 both (synthetic check, 60 claims); day 4 rerun: ECE 0.202 to 0.065, reviews 133 to 100 per 1000, cost 200 to 150 SAR (synthetic check with documents, 60) |
| E7 | Cost-based lanes vs one fixed threshold | cost_lanes_enabled | Fewer reviews for the same precision | Reviews per 1000 | Fixed threshold: 1 fewer auto approve, reviews 133 to 150 per 1000, cost 200 to 225 SAR; precision 1.0 both (synthetic check, 60) |
| E8 | Self-fix choice | self_fix_enabled | Members fix many low scores themselves | Reviews per 1000, self-fix success | With the member's fix simulated: off sends 37 of 60 to a person (617 per 1000, 925 SAR), on 10 (167 per 1000, 250 SAR); 5 of 8 fixed claims then paid right with no person (synthetic check, 60) |
| E9 | History member | history_member_enabled | Raises automation for trusted members and providers | Automation rate; false reject rate new vs tenured | Off: no lane changes, ECE 0.202 to 0.161. Fairness: payable recall new members 0.17 vs tenured 0.37 with it on AND off, false rejects 0 both, so the gap is not from this member (synthetic check, 60) |
| E11 | Reader: EasyOCR vs PaddleOCR vs Gemini free tier | reader | A vision model reads messy and Arabic receipts better than OCR plus rules | Field accuracy | pending |
| E10 | Member preview before submit | preview_enabled (simulated) | Fewer bad submissions reach the pipeline | Claims needing self-fix | pending |
| E12 | Cross-document checks | cross_checks_enabled (run-set --cross-checks on or off) | Checking patient and date across the receipt, prescription and report catches mismatches with few false alarms, and sends them to self-fix instead of approving them | cross_check_catch_rate, cross_check_false_alarm_rate, auto approve precision | Catch 3 of 3, false alarms 0 of 57, one wrong auto approve avoided (synthetic check, 60 claims, after 3 fixes) |

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

```
Run: E6, Platt calibration
Date: 2026-11-24
Commit: 9732afa (code); calibration fitted by this run, committed as config/calibration.yaml
Command: uv run reimbursement-council make-claims --count 120 --seed 11 --out data/sets/day3/tune
         uv run reimbursement-council make-claims --count 60 --seed 12 --out data/sets/day3/check
         uv run reimbursement-council run-set data/sets/day3/tune --reader easyocr --calibration off --resume
         uv run reimbursement-council fit-calibration data/sets/day3/tune/results.json
           -> a=17.1744 b=-12.5467, fitted on 102 claims (18 rejected by a hard rule left out)
         uv run reimbursement-council run-set data/sets/day3/check --reader easyocr --calibration off --results-name results_raw.json --resume
         uv run reimbursement-council run-set data/sets/day3/check --reader easyocr --calibration on --results-name results_calibrated.json --resume
Test set: synthetic check set, 60 claims (seed 12), read with EasyOCR. Fitted on the synthetic
          tune set (seed 11, 120 claims). Synthetic, not real_e2e, so not a number for slides.
Switch off: automation 0.4500, auto approve precision 1.0, payable recall 0.3556,
            false reject 0.0, correct reject 0.7333, reviews per 1000 116.7,
            self-fix per 1000 433.3, ECE 0.1551, total cost 175.00 SAR,
            heavy damage: 3 claims, all self_fix, 0 wrong auto approves.
            Lanes: auto_approve 16, auto_reject 11, self_fix 26, human_review 7.
Switch on:  automation 0.4667, auto approve precision 1.0, payable recall 0.3778,
            false reject 0.0, correct reject 0.7333, reviews per 1000 83.3,
            self-fix per 1000 450.0, ECE 0.0510, total cost 125.00 SAR,
            heavy damage: 3 claims, all self_fix, 0 wrong auto approves.
            Lanes: auto_approve 17, auto_reject 11, self_fix 27, human_review 5.
Changed lanes (2 of 60, both payable): claim_12_0058 human_review -> auto_approve, paid right;
            claim_12_0039 (light damage, payout not read) human_review -> self_fix.
Tune set, switch off, for reference: automation 0.3667, precision 1.0, false reject 0.0,
            ECE 0.1774, total cost 750.00 SAR, self-fix per 1000 383.3 (46 claims: 16 with no
            damage, 20 light, 10 unreadable), heavy damage 10 claims all self_fix.
What it means: calibration cuts the calibration error to a third (0.155 to 0.051) with no wrong
approvals and no false rejects. The cost drop (175 to 125 SAR) is only two fewer reviews, and one
of them became a self-fix, which has no cost yet (CHECK in HANDOVER), so the cost gain is small
and partly an effect of how cost is counted. 60 claims is a small set.
```

```
Run: E12, cross-document checks (patient, treatment date, provider)
Date: 2026-11-24
Commit: 0deac30 (rerun after three fixes). The first run at 507fdfd found the bugs, see below.
Command: uv run --extra ocr reimbursement-council make-claims --count 60 --seed 12 --out data/sets/docs/check
         uv run --no-sync reimbursement-council run-set data/sets/docs/check --reader easyocr --cross-checks off --results-name e12b_off.json
         uv run --no-sync reimbursement-council run-set data/sets/docs/check --reader easyocr --cross-checks on --results-name e12b_on.json
Test set: synthetic check set, 60 claims (seed 12) with document sets: 110 documents. Only 3
          claims carry a patient or date mismatch and none a missing prescription or report, so
          the document numbers rest on few claims. Calibration off. Synthetic, not real.
Switch off: lanes auto_reject 7, auto_approve 17, self_fix 28, human_review 8.
  automation_rate 0.40, auto_approve_precision 1.0, payable_recall 0.34, false_reject_rate 0.0,
  correct_reject_rate 0.70, reviews_per_1000 133.3, self_fix_per_1000 466.7, ece 0.1997,
  total_cost_sar 200.0, heavy damage: 5 claims, all self_fix, 0 wrong auto approves.
  document_kind_accuracy 0.9545 (110), missing_document_recall 0.0 (0 missing),
  missing_document_precision 0.0 (5 flagged), cross_check_catch_rate 0.0 (3),
  cross_check_false_alarm_rate 0.0 (57), expected_lane_match 0.8 (5).
Switch on: lanes auto_reject 7, auto_approve 16, self_fix 29, human_review 8.
  automation_rate 0.3833, auto_approve_precision 1.0, payable_recall 0.32, false_reject_rate 0.0,
  correct_reject_rate 0.70, reviews_per_1000 133.3, self_fix_per_1000 483.3, ece 0.2023,
  total_cost_sar 200.0, heavy damage: 5 claims, all self_fix, 0 wrong auto approves.
  document_kind_accuracy 0.9545 (110), missing_document_recall 0.0 (0 missing),
  missing_document_precision 0.0 (5 flagged), cross_check_catch_rate 1.0 (3),
  cross_check_false_alarm_rate 0.0 (57), expected_lane_match 1.0 (5).
First run (507fdfd, e12_off.json and e12_on.json in the same folder): with checks on, 19 of the
  57 claims with no mismatch had a failed cross check (false alarm rate 0.3333), automation fell
  from 0.40 to 0.25 and self_fix rose from 28 to 42. Causes, all fixed with tests before the
  rerun: (1) the QR gives the provider's Arabic name and the report was read in English, so the
  provider check compared two scripts and always failed (12 claims); (2) OCR split the label
  "اسم المريض" and "اسم" stayed in the patient name (8 claims, all light damage); (3) found
  while looking: an unclear treatment date asked the member to confirm the provider name.
What it means: the only lane change is claim_12_0016, which has another patient's name on its
  medical report. With checks off it was auto approved; with checks on it goes to self_fix and
  asks the member. No false alarms after the fixes. The 5 flagged missing documents are all
  receipts with an unreadable photo (read as "other"), which is the right thing to ask for.
  Too few document defects in this set to call it a final number.
```

```
Run: E12 on the tune set (more document defects than the check set)
Date: 2026-11-24
Commit: 0deac30
Command: uv run --extra ocr reimbursement-council make-claims --count 120 --seed 11 --out data/sets/docs/tune
         uv run --no-sync reimbursement-council run-set data/sets/docs/tune --reader easyocr --cross-checks off --results-name e12_off.json --resume
         uv run --no-sync reimbursement-council run-set data/sets/docs/tune --reader easyocr --cross-checks on --results-name e12_on.json --resume
Test set: synthetic tune set, 120 claims (seed 11), 217 documents, 7 mismatch claims, 9 missing
          documents. Calibration off. Synthetic, not real; tune sets are not for final numbers.
Switch off: lanes human_review 27, auto_approve 22, self_fix 58, auto_reject 13.
  automation_rate 0.2917, auto_approve_precision 1.0, payable_recall 0.2095,
  false_reject_rate 0.0, correct_reject_rate 0.8667, reviews_per_1000 225.0,
  self_fix_per_1000 483.3, ece 0.1544, total_cost_sar 675.0, heavy damage: 10 claims, all
  self_fix, 0 wrong auto approves. document_kind_accuracy 0.9539 (217),
  missing_document_recall 0.8889 (9), missing_document_precision 0.4444 (18),
  cross_check_catch_rate 0.0 (7), cross_check_false_alarm_rate 0.0 (113),
  expected_lane_match 0.8421 (19).
Switch on: lanes human_review 25, auto_approve 21, self_fix 61, auto_reject 13.
  automation_rate 0.2833, auto_approve_precision 1.0, payable_recall 0.2, false_reject_rate 0.0,
  correct_reject_rate 0.8667, reviews_per_1000 208.3, self_fix_per_1000 508.3, ece 0.1573,
  total_cost_sar 625.0, heavy damage: same. document metrics the same except
  cross_check_catch_rate 1.0 (7), cross_check_false_alarm_rate 0.0177 (2 of 113),
  expected_lane_match 1.0 (19).
Lane changes: 3 patient name mismatches. claim_11_0039 was auto approved with checks off and
  goes to self_fix with them on; claim_11_0035 and claim_11_0095 went to a person and now ask
  the member first.
Found: the 2 false alarms (claim_11_0034, claim_11_0068, no damage) are the Arabic patient name
  on the medical report misread by OCR at 0.57 to 0.64 confidence. The one missed missing
  prescription (claim_11_0044, light damage) had no line items read, so no category and no
  need was known. Low missing_document_precision is mostly unreadable receipts flagged as a
  missing invoice. Not tuned away; see the CHECK items in HANDOVER.
What it means: same picture as the check set with more cases. Cross checks catch every
  mismatch put in, stop a wrong auto approve, and send mismatches to the member before a
  person, which cuts reviews from 225 to 208 per 1000 and cost from 675 to 625 SAR. The price
  is 2 false alarms in 113 from OCR on Arabic names.
```

```
Run: ablations E2, E3, E5, E6, E7, E8, E9 (one switch at a time) with the fairness check
Date: 2026-11-25
Commit: 95745da (code), config_version 2d82d0d23bfe (calibration.yaml from day 3)
Command: uv run --extra ocr reimbursement-council make-claims --count 60 --seed 12 --out data/sets/abl/check
         then, with S=data/sets/abl/check and --reader easyocr on every run:
         run-set $S --results-name base.json
         run-set $S --results-name base_fix.json --simulate-fix
         run-set $S --results-name e2_off.json --set arithmetic_checks_enabled=false
         run-set $S --results-name e3_single.json --set members.coverage_checker.enabled=false
                 --set members.price_checker.enabled=false --set members.history_member.enabled=false
         run-set $S --results-name e5_off.json --set disagreement_routing_enabled=false
         run-set $S --results-name e6_on.json --calibration on
         run-set $S --results-name e7_off.json --set cost_lanes_enabled=false
         run-set $S --results-name e8_off_fix.json --set self_fix_enabled=false --simulate-fix
         run-set $S --results-name e9_off.json --set members.history_member.enabled=false
Test set: synthetic check set with documents, 60 claims (seed 12), the same claims as E12, plus the
          fixed file of each fixable defect (8 files). Synthetic, not real. The base is the
          config as it is (calibration off). Every run processed all 60 claims.

                            base  e2_off e3_one  e5_off  e6_on  e7_off  e9_off  base+fix e8_off+fix
automation_rate            0.383  0.333  0.400   0.400   0.383  0.367   0.383   0.433    0.383
auto_approve_precision     1.0    1.0    1.0     1.0     1.0    1.0     1.0     1.0      1.0
payable_recall             0.32   0.32   0.34    0.34    0.32   0.30    0.32    0.38     0.32
false_reject_rate          0.0    0.0    0.0     0.0     0.0    0.0     0.0     0.0      0.0
correct_reject_rate        0.70   0.40   0.70    0.70    0.70   0.70    0.70    0.70     0.70
reviews_per_1000           133.3  133.3  116.7   116.7   100.0  150.0   133.3   166.7    616.7
self_fix_per_1000          483.3  533.3  483.3   483.3   516.7  483.3   483.3   400.0    0.0
ece                        0.2023 0.2044 0.1609  0.2023  0.0654 0.2023  0.1608  0.1762   0.2023
total_cost_sar             200    200    175     175     150    225     200     250      925
heavy_damage_wrong_approves 0     0      0       0       0      0       0       0        0
self-fix tried / paid right                                                     8 / 5    0
fairness, payable claims: new members (fewer than 3 past claims) 12, tenured 38 in every run.
  false_reject_rate new 0.0 and tenured 0.0 in every run.
  payable_recall new 0.1667 in every run; tenured 0.3684 (base, e2, e6, e9, e8),
  0.3947 (e3, e5), 0.3421 (e7), 0.4474 (base+fix).

Lane changes against base, claim by claim (checked by hand before writing this):
- E2 off: claim_12_0000, 0010, 0053 (excluded service) go from auto_reject to self_fix. Passed
  checks raise the confidence of the line items; without them the exclusion rule is not sure,
  so it asks the member instead of rejecting.
- E3 one member and E5 off: claim_12_0055 (overpriced) goes from human_review to auto_approve,
  paid right at the network price. The price checker's low vote made the council disagree.
- E6 on: claim_12_0005 (over limit) and claim_12_0039 (clean) go from human_review to self_fix.
- E7 off: claim_12_0036 (overpriced) goes from auto_approve to human_review.
- E9 off: no lane changes.
- base+fix: 5 of the 8 fixed claims (4 unreadable photos, 1 patient mismatch) are then auto
  approved and paid right. Two clean claims (claim_12_0038, 0051) that were auto approved go to
  a person as "possible duplicate": once the unreadable receipts are read clearly, their weak key
  (VAT number, date, total) matches these claims. This is the weak-key CHECK from data review 4.
What it means: on this small synthetic set no switch changed precision (1.0 everywhere) or caused
  a false reject. Calibration (E6) and self-fix (E8) change the most: self-fix with the member's
  fix keeps 27 of 60 claims away from a person. Arithmetic checks matter for confident rejects
  (E2). The council's extra members and disagreement routing (E3, E5) cost one review on one
  overpriced claim and did not catch a wrong approval here. Each change is one to three claims of
  60, so none of these is a final number.
```
