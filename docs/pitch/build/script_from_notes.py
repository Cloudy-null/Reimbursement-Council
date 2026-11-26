"""Write the presenter's read-aloud script from the deck's speaker notes (one section per slide).

Run: python script_from_notes.py deck.pptx script.md
"""

import re
import sys
from pathlib import Path

from pptx import Presentation

deck, out = Path(sys.argv[1]), Path(sys.argv[2])
prs = Presentation(str(deck))


def _title(slide) -> str:
    """The slide's title: the text set in the largest font (the template has no title placeholders)."""
    best, size = "", 0
    for s in slide.shapes:
        if not s.has_text_frame or not any(c.isalpha() for c in s.text_frame.text):
            continue
        runs = [r for p in s.text_frame.paragraphs for r in p.runs if r.font.size]
        largest = max((r.font.size.pt for r in runs), default=0)
        if largest > size:
            best, size = s.text_frame.text.strip().replace("‎", ""), largest
    return best

parts = [
    "# Reimbursement Council: presenter script (v2)",
    "",
    "Read this aloud, slide by slide. It is the same text as the speaker notes in "
    f"{deck.name}. Times are targets; the whole talk is about 12 minutes, then questions.",
    "Numbers: say \"synthetic\" or \"real\" with each one. Sources are listed under each slide "
    "and are not read aloud.",
    "",
]
total = 0
for number, slide in enumerate(prs.slides, 1):
    title = _title(slide)
    notes = slide.notes_slide.notes_text_frame.text.strip() if slide.has_notes_slide else ""
    lines = [line.strip() for line in notes.splitlines() if line.strip()]
    timing = lines.pop(0) if lines and lines[0].lower().startswith("about") else ""
    seconds = re.search(r"about (\d+) (second|minute)", timing.lower())
    if seconds:
        total += int(seconds.group(1)) * (60 if seconds.group(2) == "minute" else 1)
    sources = [line for line in lines if line.startswith("Sources:")]
    spoken = [line for line in lines if not line.startswith("Sources:")]
    parts.append(f"## Slide {number}: {title.splitlines()[0] if title else ''}")
    if timing:
        parts.append(f"*{timing}*")
    parts.append("")
    parts.extend(f"{line}\n" for line in spoken)
    if sources:
        parts.append(f"> {sources[0]}\n")
minutes, rest = divmod(total, 60)
parts.append(f"Total planned speaking time: {minutes} min {rest} s.")
out.write_text("\n".join(parts) + "\n", encoding="utf-8", newline="\n")
print("script", out, f"{minutes}:{rest:02d}")
