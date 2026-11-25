# 009: jsonschema for the export check, pypdfium2 for PDFs

Date: 2026-11-25
Status: Accepted by Claude in overnight mode; owner to review.

## Context
The brief asks for structured, submission-ready claim data (deliverable 2), and says documents
arrive as photos, scans and PDFs. We needed a way to prove every export follows a published
schema, and a way to read PDFs with the reader we already have.

## Options
- Export check: validate with our own pydantic model only; validate with a JSON Schema
  validator against the committed schema file (jsonschema).
- PDF: pypdfium2 (pdfium, the PDF engine in Chrome; pip wheels, no system install);
  pdf2image (needs Poppler installed on the machine); PyMuPDF (AGPL license).

## Choice
- jsonschema 4.26.0. The schema file is generated from the model and committed. The check runs
  against the file, the way a claims system would, so a drift between file and model is caught
  (a test also compares them).
- pypdfium2 5.15.2. Up to `max_pdf_pages` pages (config/documents.yaml) are drawn at
  `pdf_render_scale` into one tall PNG, so one PDF stays one document and the QR finder and OCR
  work unchanged. A scanned PDF is images inside a PDF, so it takes the same path.

## Trade-off
- Two more dependencies (jsonschema brings referencing and rpds-py). Both are common and pinned.
- Pages after `max_pdf_pages` are not read. A PDF with text but no images is drawn and read by
  OCR, not by its text layer: simpler, and the same path for digital and scanned PDFs, but slower
  and less exact than reading the text layer.
- TIFF scans are not taken yet.
