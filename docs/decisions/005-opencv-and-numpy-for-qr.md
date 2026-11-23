# 005: OpenCV and numpy to read QR codes from images

Date: 2026-11-23
Status: Accepted

## Context
Many Saudi receipts carry a ZATCA QR code. Reading it first gives the seller, VAT number, time, total and VAT with full confidence. We need to find and read QR codes in a photo, offline, on Windows and Linux, with no system packages.

## Options
- pyzbar: small, but needs the zbar system library, which is not there by default on Windows.
- qreader or other deep learning readers: better on bad photos, but large downloads.
- OpenCV (opencv-python-headless): one pip wheel, reads QR codes with QRCodeDetector, and can also make QR images, which the tests use.

## Choice
opencv-python-headless 5.1.0.95, pinned. numpy 2.5.5 is pinned too, because OpenCV needs it and our adapter uses it directly (np.frombuffer) to turn file bytes into an image. Both live only in reimbursement_council/adapters/qr_image.py. Core never imports them.

## Trade-off
OpenCV is a big wheel (about 46 MB) for one feature. We accept that because it installs with no system packages and works offline. If QR reading on real phone photos turns out weak, a later decision can add a fallback reader behind the same adapter.
