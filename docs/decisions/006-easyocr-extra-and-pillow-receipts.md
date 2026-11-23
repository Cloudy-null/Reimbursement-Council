# 006: EasyOCR as an optional extra, Pillow for synthetic receipts

Date: 2026-11-24
Status: Accepted by Claude in overnight mode; owner to review.

## Context
Layer 1 needs an offline reader for Arabic and English receipts (spec 5, decision 004) and test receipts with known answers, because the owner has no real receipts for the demo.

## Options
- Reader: EasyOCR (spec default), PaddleOCR, or a vision model (needs a key and the internet).
- Where it lives: a main dependency, or an optional extra.
- Receipt images: Pillow drawing, HTML rendered in headless Chrome, or a few hand-made images.

## Choice
- EasyOCR 1.7.2 with PyTorch, in an optional `ocr` extra (`uv sync --extra ocr`). It is imported only when the first image is read. CI and unit tests do not install it; parsing is tested on real EasyOCR output saved as JSON in tests/fixtures/ocr.
- OCR results are cached on disk by image hash plus engine name (spec section 11), so reruns are fast and the same.
- Receipts are drawn with Pillow. Arabic is joined with arabic-reshaper and ordered with python-bidi. Fonts (IBM Plex Sans Arabic, OFL) are bundled in assets/fonts so every machine draws the same pixels.

## Trade-off
PyTorch is a large download and EasyOCR reads one receipt in about 6 to 10 seconds on a laptop CPU. The website loads the model on the first upload. Pillow receipts look plainer than real ones and come from our own layouts, so accuracy on them is an upper bound until real receipts are tested.
