# Layer 1: Reading receipt photos

Date: 2026-11-23
Owner: Abdulrahman Aljahdali
Status: Written by Claude in overnight mode after the owner said "make what we can, do it". Not reviewed by the owner yet. Every choice below that the owner did not make is marked "Claude's call".

## Why
The walking skeleton reads a receipt only from a hand-written reading file, and an image gives only its QR code. Layer 1 of the main spec (section 9) is done when a receipt image goes in and stored fields plus hard rule results come out. The owner has no real receipts for the demo, so the demo receipts are ones we generate (owner's answer, 2026-11-23).

## Goals
- A receipt maker that draws Saudi style medical receipt images (Arabic and English, ZATCA QR or not) and saves the true value of every field next to each image.
- An offline reader: EasyOCR text plus rules that turn the text into the same fields and line items the pipeline already uses, each with a confidence.
- A command that measures field accuracy of the reader on generated receipts, so the numbers in EXPERIMENTS.md come from a run, not a guess.

## Non-goals (this layer)
- PDFs, Hijri-only dates, handwritten receipts.
- Training an OCR model. We use EasyOCR's own models.
- Real receipt datasets. Their licenses are still a CHECK.

## Anti-goals
- A reader that only works on our own layout. The maker draws more than one layout and the parser finds fields by their label words, not by position.
- Tests that need PyTorch. Parsing is pure logic and is tested with fake OCR lines. Only one optional slow test runs the real OCR.

## Approaches considered (for making images)
1. Draw with Pillow, Arabic joined with arabic-reshaper and python-bidi. Fast, pure Python, and we know every field's box. Picked.
2. Render the preview page HTML in headless Chrome with Playwright. Perfect Arabic, but a big extra download, slower, more to break.
3. Hand-make 10 to 20 receipts. Too few to measure anything.

The owner handed the how to Claude; option 1 is Claude's call.

## Design

### Receipt maker (synthetic)
- `reimbursement_council/synthetic/receipt_content.py` (pure): builds a `ReceiptContent` from a seeded random generator: layout, provider (Arabic and English names, VAT number), invoice number, local time, patient, file number, line items from the price list (plus some items not on it), subtotal, VAT, total, whether it has a QR, and the true fields.
- `reimbursement_council/adapters/receipt_drawing.py`: draws a `ReceiptContent` to a PNG with Pillow, using fonts bundled in `assets/fonts/` (IBM Plex Sans Arabic, OFL license). Optional damage: blur, small rotation, noise, JPEG quality.
- Layouts (Claude's call): `clinic_bilingual`, `pharmacy_bilingual`, `clinic_arabic_first`. Label words differ a little between them.
- Each image gets `<name>.png` and `<name>.truth.json`.

### Reader
- `reimbursement_council/adapters/ocr_engine.py`: wraps EasyOCR (`['ar', 'en']`, CPU). Imported lazily, so the app still runs without it. Output: `OcrLine(text, confidence, box)`.
- `reimbursement_council/adapters/ocr_cache.py`: caches OCR lines on disk by image hash plus engine name plus version (main spec section 11), under `data/cache/ocr/`.
- `reimbursement_council/core/receipt_parsing.py` (pure): groups OCR lines into rows, finds labels in Arabic and English, reads money, VAT number, date and time, patient, provider and line items, and matches item text to service codes using aliases in `config/prices.yaml`.
- Confidence of a field is the OCR confidence of its value, multiplied by `ocr.pattern_miss_factor` when the value does not match its pattern, and by `ocr.heuristic_factor` when it was found by position (provider name) rather than by a label. Line item confidence drops when quantity times unit price is not the amount. All factors in `config/decision.yaml`.
- `QrOcrReader` = QR codes (existing) plus OCR text. `reader_for` uses it for images when the `reader` setting is `easyocr`, and falls back to QR only when it is `qr_only`.
- Dependencies (Claude's call, decision record 006): `easyocr` and its PyTorch in an optional `ocr` extra, so CI and the core stay light. `pillow`, `arabic-reshaper` and `python-bidi` in the main set for the maker.

### Measuring
- `reimbursement-council make-receipts --count N --seed S --out data/receipts/<set>` writes images and truths.
- `reimbursement-council read-accuracy data/receipts/<set>` reads each image (cached), compares with truth, and prints per-field accuracy and line item code accuracy. Results go into docs/EXPERIMENTS.md with the command and commit.

## Left to the builder
Exact label lists, row grouping tolerance, fonts sizes and layout details, damage strengths.

## Spike result (2026-11-23, Windows CPU)
- EasyOCR 1.7.2 with PyTorch 2.15 installs and runs on Python 3.12. Models download once (about 100 MB) into the user's .EasyOCR folder. Load about 13 to 28 seconds, one receipt about 6 seconds.
- Money values read perfectly (confidence 1.00). Arabic labels such as "الإجمالي" read.
- Mistakes the parser must handle: VAT number read with letter O for zero ("3OOOOOO00000003"), "VAT" read as "٧AT", a lone quantity "1" missed, the patient line read with low confidence (0.27).
- Decision: go with EasyOCR. The parser fixes O to 0 inside digit runs, knows common label misreads, and infers quantity from amount and unit price.
