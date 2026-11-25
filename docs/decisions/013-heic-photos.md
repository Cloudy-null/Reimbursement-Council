# 013: HEIC photos are turned into JPEG on upload

Date: 2026-11-25. Status: accepted.

Context: iPhones save photos as HEIC by default. Pillow cannot open HEIC by itself, so a member
on an iPhone could not upload a photo straight from the camera roll.

Options: ask members to change their camera setting (friction); convert in the browser
(JavaScript, more moving parts); convert on the server with the pillow-heif library.

Choice: pillow-heif 1.9.0 (pinned), used only in adapters/heic.py when a .heic or .heif file is
uploaded. The JPEG is stored and read like any other photo; a file that is not a real HEIC image
is refused as a wrong type.

Trade-off: one more library with native code (libheif) to install and keep updated.
