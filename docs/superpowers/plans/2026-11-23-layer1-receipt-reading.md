# Layer 1 Receipt Reading Implementation Plan

> Written by Claude in overnight mode, executed natively in the same session. Owner review pending.

**Goal:** A receipt photo goes in; fields, line items and hard rule results come out, read offline with EasyOCR. Accuracy is measured on generated receipts.

**Spec:** docs/superpowers/specs/2026-11-23-layer1-receipt-reading-design.md (and the main spec, section 9, layer 1)

## Global Constraints
- Same as the walking skeleton plan: Python 3.12 with uv, pinned dependencies, money in halalas, every number in config, core does no I/O, logging not print, files under about 300 lines, plain English, no em dashes, commits `<type>: <what>` with no co-author lines.
- Branch `build/overnight`. Never merge to main. After each task: commit, update HANDOVER "Current status" and "Next 3 tasks", commit.
- PyTorch and EasyOCR live only in the optional `ocr` extra. CI does not install it. No unit test imports easyocr; the one real OCR test is marked `slow` and skips when easyocr is missing.
- Generated images and caches go under `data/` (gitignored). Only code, config, fonts and tiny test fixtures are committed.

## Tasks
1. **Spike.** Install EasyOCR in the `ocr` extra, read one drawn Arabic and English image, note speed and quality. Throwaway; decide go or fallback.
2. **Price list aliases and more services.** `PriceListItem.aliases: list[str]` (Arabic and English names). Add services and categories (radiology, dental) to prices and the silver tier. Tests: config loads; every alias is unique to one code.
3. **Receipt content (pure).** `make_receipt_content(rng, layout, options) -> ReceiptContent` with true fields. Tests: totals add up, VAT is 15 percent, QR payload decodes to the true values, same seed gives the same receipt.
4. **Receipt drawing (adapter).** `draw_receipt(content) -> DrawnReceipt(png_bytes, boxes)`, damage options. Tests: PNG decodes, QR in the image reads back with OpenCV, Arabic text is shaped (not the raw letters), boxes inside the image.
5. **Receipt parser (pure).** `parse_receipt_lines(lines, settings) -> ReaderOutput`. Tests with fake OCR lines: each field by its English and Arabic label, Arabic-Indic digits, VAT number pattern, date and time, line items with quantity check, item matched by alias, unlisted item has no code, low OCR confidence carried through, "VAT No." is not read as VAT amount, "Subtotal" is not read as total.
6. **EasyOCR engine, cache and reader.** `EasyOcrEngine.read(image_bytes) -> list[OcrLine]`, disk cache by image hash, `QrOcrReader`, `reader` setting, `reader_for(document, settings)`. Tests: cache round trip with a fake engine, reader combines QR and parsed text, missing easyocr gives a clear error. One slow test reads a drawn receipt for real.
7. **Commands and accuracy.** `make-receipts` and `read-accuracy` in the CLI. Run on 60 generated receipts, record per-field accuracy in EXPERIMENTS.md with command and commit. Tag `layer-1`.
