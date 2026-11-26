"""Build docs/pitch/Reimbursement_Council_Final.pptx from the duplicated template skeleton."""

import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = Path("D:/rc-tmp/pitch")
SHOTS = HERE / "shots"
ICONS = HERE / "icons"
OUT = Path(sys.argv[1])
FACTS = {"tests": sys.argv[2], "e2e": sys.argv[3], "commit": sys.argv[4]}

PURPLE, DARK, GREY, INK = "4F29B7", "3B2581", "545454", "2E2A3D"
LAV, LAV2, BORDER, WHITE, TEAL, TINT = "CFC4F5", "DDD3F7", "E6E2F0", "FFFFFF", "57E3D8", "EFEBFA"
ORANGE = "F4A259"
HEAD, BODY = "IBM Plex Sans Arabic Bold", "Open Sans"
TAGS = {
    "Real": ("D5F7F4", "1FA89D", "0B5E58"),
    "Synthetic": ("FDE8D2", "E08A2E", "7A420C"),
    "Code": ("EFEBFA", PURPLE, DARK),
}

prs = Presentation(str(HERE / "skel.pptx"))
S = list(prs.slides)


def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


def shape(slide, name):
    for s in slide.shapes:
        if s.name == name:
            return s
    raise KeyError(name)


def delete(slide, *names):
    for n in names:
        el = shape(slide, n)._element
        el.getparent().remove(el)


def set_text(sh, text, size=None, color=None, width=None):
    tf = sh.text_frame
    p0 = tf.paragraphs[0]
    runs = p0.runs
    for extra in tf.paragraphs[1:]:
        extra._p.getparent().remove(extra._p)
    for r in runs[1:]:
        r._r.getparent().remove(r._r)
    runs[0].text = text
    if size:
        runs[0].font.size = Pt(size)
    if color:
        runs[0].font.color.rgb = rgb(color)
    if width:
        sh.width = Inches(width)
    tf.word_wrap = True


def text(slide, x, y, w, h, paras, size=20, color=GREY, font=BODY, bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, space=6, line=None):
    """paras: list of str or list of (text, dict) runs."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space)
        if line:
            p.line_spacing = line
        runs = [(para, {})] if isinstance(para, str) else para
        for t, o in runs:
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = o.get("font", font)
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.color.rgb = rgb(o.get("color", color))
    return box


def card(slide, x, y, w, h, fill=WHITE, line=BORDER, radius=0.06):
    c = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    c.adjustments[0] = radius
    c.fill.solid()
    c.fill.fore_color.rgb = rgb(fill)
    if line:
        c.line.color.rgb = rgb(line)
        c.line.width = Pt(1.5)
    else:
        c.line.fill.background()
    c.shadow.inherit = False
    c.text_frame.text = ""
    return c


def tag(slide, x, y, kind, n, w=None):
    fill, edge, ink = TAGS[kind]
    label = f"{kind}, n={n}" if n else kind
    w = w or 0.2 + 0.125 * len(label)
    c = card(slide, x, y, w, 0.38, fill=fill, line=edge, radius=0.5)
    tf = c.text_frame
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = BODY, Pt(15), True, rgb(ink)
    return w


def square(slide, x, y, color, size=0.36):
    card(slide, x, y, size, size, fill=color, line=None, radius=0.22)


def labeled(label, sentence, lsize=21, ssize=19, lcolor=PURPLE):
    return [(label + " ", {"bold": True, "color": lcolor, "size": lsize, "font": HEAD}),
            (sentence, {"size": ssize})]


def framing(slide, line, y=2.25, x=1.81):
    text(slide, x, y, 14.6, 0.6, [line], size=24, color=GREY)


SOURCES = {}


def footer(slide, line):
    """Sources go in the speaker notes: on the slide the template's squares cover them."""
    SOURCES[slide.slide_id] = line


def notes(slide, words):
    extra = SOURCES.get(slide.slide_id)
    tail = "\n" + "Sources: " + extra if extra else ""
    slide.notes_slide.notes_text_frame.text = words + tail


def picture(slide, path, x, y, w, h, border=LAV):
    im = Image.open(path)
    ratio = im.width / im.height
    if w / h > ratio:
        pw, ph = h * ratio, h
    else:
        pw, ph = w, w / ratio
    pic = slide.shapes.add_picture(str(path), Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2),
                                   Inches(pw), Inches(ph))
    pic.line.color.rgb = rgb(border)
    pic.line.width = Pt(2)
    return pic


# 1. Title -----------------------------------------------------------------------------------
s = S[0]
set_text(shape(s, "TextBox 9"), "Reimbursement Council", size=88)
set_text(shape(s, "TextBox 12"), "Upload it. We read it. You check it. Done.", width=15)
notes(s, "About 20 seconds.\n"
      "Good morning. We are the Reimbursement Council team.\n"
      "Our whole idea fits in one line: you upload it, we read it, you check it, done.\n"
      "Let me start with the problem.")

# 2. Problem ---------------------------------------------------------------------------------
s = S[1]
set_text(shape(s, "TextBox 10"), "Typing what is already there")
framing(s, "From the brief: members re-type, and claims teams re-check.")
box = shape(s, "Group 4")
box.left, box.top, box.width, box.height = Inches(1.0), Inches(3.0), Inches(17.4), Inches(3.55)
bulb = shape(s, "Freeform 9")
bulb.left, bulb.top, bulb.width, bulb.height = Inches(1.55), Inches(3.55), Inches(1.3), Inches(1.3)
delete(s, "TextBox 11")
text(s, 3.3, 3.3, 14.6, 0.5, ["The problem statement, in the brief's own words"], size=20, color=TEAL, font=HEAD)
text(s, 3.3, 3.85, 14.6, 2.6, [
    "\u201cHow might we eliminate manual data entry from the reimbursement claim journey by using "
    "AI to read, validate, and structure documents, so that members submit right the first time "
    "and claims teams receive processing-ready data?\u201d"], size=27, color=WHITE, font=HEAD, line=1.1)
cw = (17.4 - 0.8) / 3
items = [
    ("Members.", "They re-type information that already exists in their documents. This causes "
     "friction, submission errors, avoidable rejections and delays.", False),
    ("Claims teams.", "They spend effort validating documents, finding missing information and "
     "re-keying data for internal systems.", False),
    ("Our answer.", "The member uploads. The system reads, validates, flags gaps and hands over "
     "clean, structured data.", True),
]
for i, (label, sentence, hot) in enumerate(items):
    x = 1.0 + i * (cw + 0.4)
    card(s, x, 6.9, cw, 3.55, fill=DARK if hot else WHITE, line=None if hot else BORDER)
    square(s, x + 0.35, 7.25, [ORANGE, PURPLE, TEAL][i])
    text(s, x + 0.35, 7.8, cw - 0.7, 2.5,
         [labeled(label, sentence, 25, 22, TEAL if hot else PURPLE)],
         color=WHITE if hot else GREY)
notes(s, "About 50 seconds.\n"
      "This is the brief's own problem statement. Remove manual typing, check before submit, "
      "and give the claims team clean data.\n"
      "Today the member types what is already printed on the invoice. Small typing mistakes "
      "turn into rejections and delays.\n"
      "On the other side, a person opens every document, looks for what is missing, and types "
      "it again into an internal system.\n"
      "Our answer: the member uploads, and the system reads, checks, flags the gaps and hands "
      "over clean, structured data.")

# 3. Stack -----------------------------------------------------------------------------------
s = S[2]
# The template has a picture placeholder where the club logo sits on every other slide.
logo_rid = shape(S[3], "Group 33")._element.xpath(".//a:blip/@r:embed")[0]
stack_rid = shape(s, "Group 11")._element.xpath(".//a:blip/@r:embed")[0]
s.part.rels[stack_rid]._target = S[3].part.related_part(logo_rid)
for fill in shape(s, "Group 11")._element.xpath(".//a:fillRect"):
    for side, value in (("l", "0"), ("t", "-129"), ("r", "0"), ("b", "-130")):
        fill.set(side, value)
shape(s, "Group 11").left = shape(S[3], "Group 33").left
set_text(shape(s, "TextBox 9"), "Our stack")
framing(s, "Open tools, all running on one PC with one GPU.")
delete(s, "Group 4", "Group 13", "Group 15", "Group 17", "TextBox 19", "TextBox 20",
       "TextBox 21", "TextBox 22", "Group 23", "Group 26", "Group 29", "Group 32")
stack = [
    ("python", "Python", "Every layer, typed and tested."),
    ("fastapi", "FastAPI", "The website and its routes, kept thin."),
    ("sqlite", "SQLite", "Claims, decisions and reviews in one local file."),
    (None, "EasyOCR", "Reads the text on every photo."),
    ("pytorch", "PyTorch + CUDA", "Runs EasyOCR on one RTX 4070 Super."),
    ("ollama", "Ollama + Qwen3-VL", "Our local AI reader and case reviewer."),
    ("json", "JSON + FHIR R4", "Every export checked against a JSON Schema."),
    ("pytest", "Playwright + pytest", "Unit tests and a real browser test."),
    ("githubactions", "GitHub Actions", "Lint, types and tests on every push."),
]
cw, ch = (17.4 - 0.8) / 3, 1.8
for i, (icon, name, line) in enumerate(stack):
    x, y = 1.0 + (i % 3) * (cw + 0.4), 4.75 + (i // 3) * (ch + 0.22)
    card(s, x, y, cw, ch)
    if icon:
        s.shapes.add_picture(str(ICONS / f"{icon}.png"), Inches(x + 0.32), Inches(y + 0.4),
                             Inches(1.0), Inches(1.0))
    else:
        b = card(s, x + 0.32, y + 0.4, 1.0, 1.0, fill=PURPLE, line=None, radius=0.18)
        tf = b.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = tf.margin_right = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = "OCR"
        r.font.name, r.font.size, r.font.bold, r.font.color.rgb = HEAD, Pt(22), True, rgb(WHITE)
    text(s, x + 1.6, y + 0.28, cw - 1.85, 0.5, [name], size=23, color=DARK, font=HEAD)
    text(s, x + 1.6, y + 0.86, cw - 1.85, 0.9, [line], size=18, color=GREY)
notes(s, "About 30 seconds.\n"
      "Quickly, what it is built with. Python and FastAPI for the website, SQLite for storage.\n"
      "EasyOCR reads the text, on our own graphics card. Qwen3-VL through Ollama is a local AI "
      "model that reads the documents and gives a second opinion on a case.\n"
      "Every export is checked against a JSON schema and maps to FHIR R4. Tests run on every "
      "push. Nothing here is a paid cloud service.")

# 4a-4d: the four "why it fits" slides --------------------------------------------------------
PILLS = [("Group 6", "TextBox 25"), ("Group 16", "TextBox 26"), ("Group 19", "TextBox 27"),
         ("Group 22", "TextBox 28")]
CARDS = ("Group 4", "Group 10", "Group 12", "Group 14", "TextBox 29", "TextBox 30", "TextBox 31",
         "TextBox 32")


def fit_slide(slide, active, title, line):
    set_text(shape(slide, "TextBox 9"), title)
    framing(slide, line)
    delete(slide, *CARDS)
    for i, (g, t) in enumerate(PILLS):
        grp, label = shape(slide, g), shape(slide, t)
        grp.top -= Inches(0.85)
        label.top -= Inches(0.85)
        if i != active:
            body = grp.shapes[0]
            body.fill.solid()
            body.fill.fore_color.rgb = rgb(BORDER)
            label.text_frame.paragraphs[0].runs[0].font.color.rgb = rgb("8A7FB5")
        else:
            label.text_frame.paragraphs[0].runs[0].font.color.rgb = rgb(WHITE)


# 4a Need
s = S[3]
fit_slide(s, 0, "The member sends blind", "Need and problem: from Bupa's own FAQ and one real claim.")
cw = (17.4 - 0.8) / 3
top, hgt = 4.45, 6.0
card(s, 1.0, top, cw, hgt)
square(s, 1.35, top + 0.35, ORANGE)
text(s, 1.35, top + 0.9, cw - 0.7, 0.6, ["Bupa's own FAQ"], size=26, color=PURPLE, font=HEAD)
text(s, 1.35, top + 1.55, cw - 0.7, 1.0, ["The most common reasons a claim waits or is rejected:"],
     size=20)
reasons = ["Missing eye test", "Missing tooth number", "Missing prescription or report",
           "Invalid invoice", "Service not covered"]
for i, r in enumerate(reasons):
    yy = top + 2.75 + i * 0.6
    square(s, 1.4, yy + 0.1, PURPLE, size=0.22)
    text(s, 1.8, yy, cw - 1.2, 0.5, [r], size=21, color=INK)
x2 = 1.0 + cw + 0.4
card(s, x2, top, cw, hgt, fill=DARK, line=None)
text(s, x2 + 0.35, top + 0.35, cw - 2.6, 0.6, ["One real claim"], size=26, color=TEAL, font=HEAD)
tag(s, x2 + cw - 1.95, top + 0.42, "Real", 1, w=1.6)
text(s, x2 + 0.35, top + 1.2, cw - 0.7, 0.5, ["The member sent"], size=20, color=LAV)
text(s, x2 + 0.35, top + 1.6, cw - 0.7, 1.0, ["1,750 SAR"], size=50, color=WHITE, font=HEAD)
text(s, x2 + 0.35, top + 2.7, cw - 0.7, 0.5, ["Bupa paid"], size=20, color=LAV)
text(s, x2 + 0.35, top + 3.1, cw - 0.7, 1.0, ["450 SAR"], size=50, color=TEAL, font=HEAD)
text(s, x2 + 0.35, top + 4.3, cw - 0.7, 1.6, [
    "The member learned why only after: 1,200 SAR over the frame limit and a 100 SAR member share."],
    size=19, color=WHITE)
x3 = 1.0 + 2 * (cw + 0.4)
card(s, x3, top, cw, hgt)
square(s, x3 + 0.35, top + 0.35, TEAL)
text(s, x3 + 0.35, top + 0.9, cw - 0.7, 0.6, ["Our journey analysis"], size=26, color=PURPLE, font=HEAD)
text(s, x3 + 0.35, top + 1.65, cw - 0.7, 4.2, [
    "The problem starts at the moment of sending.",
    "The member is blind: no idea what will be paid, or what is missing.",
    [("So the fix belongs before send.", {"bold": True, "color": PURPLE, "font": HEAD})]],
    size=22, color=INK, space=14)
footer(s, "Real claim: docs/pitch/real_claim_case.md at a8dd032, used with the member's consent.")
notes(s, "About 45 seconds.\n"
      "Why does this matter for Bupa? Bupa's own FAQ lists why claims wait or get rejected: "
      "a missing eye test, a missing tooth number, a missing prescription, an invalid invoice, "
      "a service that is not covered.\n"
      "Here is a real Bupa claim, used with the member's permission. The member sent 1,750 "
      "riyals. Bupa paid 450. The member only found out why afterwards: the frame limit and the member share.\n"
      "So the problem starts at the moment of sending. The member is blind. That is where we "
      "put our fix.")

# 4b Value
s = S[4]
fit_slide(s, 1, "The payout, before send",
          "Added value: one real claim, our synthetic tests, and a clearly marked estimate.")
card(s, 1.0, 4.4, 17.4, 1.1, fill=DARK, line=None)
text(s, 1.4, 4.4, 14.0, 1.1, ["Before she pressed send, we told her 450. Bupa paid 450."],
     size=30, color=WHITE, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
tag(s, 16.4, 4.76, "Real", 1, w=1.6)
tiles = [
    ("27 of 30", "Bad claims caught before payment", [("Synthetic", 30)]),
    ("21 of 21", "Approvals that were right", [("Synthetic", 21), ("Real", 50)]),
    ("0 of 50", "Good claims wrongly rejected", [("Synthetic", 50), ("Real", 50)]),
    ("31 of 60", "Claims decided with no person", [("Synthetic", 60)]),
    ("8.057 s", "Per claim, through the website", [("Synthetic", 9)]),
]
tw = (17.4 - 4 * 0.3) / 5
for i, (value, label, kinds) in enumerate(tiles):
    x = 1.0 + i * (tw + 0.3)
    card(s, x, 5.75, tw, 2.75)
    text(s, x + 0.25, 5.9, tw - 0.5, 0.8, [value], size=40, color=PURPLE, font=HEAD)
    text(s, x + 0.25, 6.8, tw - 0.5, 0.8, [label], size=18, color=INK)
    for k, (kind, n) in enumerate(kinds):
        tag(s, x + 0.25, 7.55 + k * 0.43, kind, n)
card(s, 1.0, 8.75, 17.4, 1.75, fill=TINT, line=LAV)
text(s, 1.35, 8.85, 16.7, 1.6, [
    [("Estimate, not measured. ", {"bold": True, "color": "7A420C", "font": HEAD}),
     ("Assumptions: a member types for 5 to 8 minutes per claim today; a manual review takes "
      "6 to 10 minutes (midpoint 8).", {})],
    [("Review time saved per 1,000 claims = 1,000 x 31/60 decided with no person x 8 min "
      "= 4,133 min, about 68 hours.", {"bold": True, "color": DARK})],
], size=19, color=INK, space=8)
footer(s, "Sources: synthetic check set at 120febe, real e2e at ac2a7e4, speed at 09b4717 "
          "(docs/pitch/numbers.md).")
notes(s, "About 50 seconds.\n"
      "Our value in one sentence: before she pressed send, we told her 450, and Bupa paid 450. "
      "That is the real claim from the last slide.\n"
      "On our synthetic test set, where we know the right answers: we caught 27 of 30 bad claims "
      "before payment. Every one of our 21 automatic approvals was right. We rejected none of "
      "the 50 good claims. 31 of 60 claims needed no person at all. And on 50 real receipts: no "
      "wrong approval and no wrong rejection.\n"
      "A claim takes about 8 seconds through the website.\n"
      "The bottom line is an estimate, and we say so. If a review takes about 8 minutes, then "
      "31 of every 60 claims needing no person saves about 68 review hours per 1,000 claims.")

# 4c Edge
s = S[5]
fit_slide(s, 2, "More than reading a form",
          "Competitive edge: we check, explain and route the claim, not only extract it.")
edges = [
    ("Checks before submit.", "Missing papers and broken rules show before the member sends."),
    ("A confidence score per field.", "Unsure values go to the member to confirm, not to a guess."),
    ("Payout and reason first.", "The expected amount, and why, shown before sending."),
    ("A council with numeric votes.", "Each check gives a number. The votes pick the path."),
    ("Bupa's own rules built in.", "VAT not paid, a 20 percent share up to 100 SAR, the frame "
     "limit, eye test, tooth number."),
    ("Arabic and English.", "Every screen in both, right to left done right."),
    ("Arabic-Indic digits.", "Matched digit by digit to the print. Unsure ones go to the member."),
    ("HEIC and PDF.", "iPhone photos and PDF invoices work as they are."),
]
cw, ch = (17.4 - 0.9) / 4, 2.9
for i, (label, sentence) in enumerate(edges):
    x, y = 1.0 + (i % 4) * (cw + 0.3), 4.45 + (i // 4) * (ch + 0.25)
    card(s, x, y, cw, ch)
    square(s, x + 0.3, y + 0.3, [ORANGE, PURPLE, TEAL, LAV][i % 4])
    text(s, x + 0.3, y + 0.85, cw - 0.6, 0.9, [label], size=21, color=PURPLE, font=HEAD)
    text(s, x + 0.3, y + 1.6, cw - 0.6, 1.3, [sentence], size=18, color=GREY)
notes(s, "About 40 seconds.\n"
      "Most tools stop at reading a form. We go further.\n"
      "We check before the member sends. Every field has a confidence score, and unsure values "
      "go back to the member. The member sees the payout and the reason first.\n"
      "A council of checks votes with numbers, and the votes choose the path: approve, ask the "
      "member, a person, or reject.\n"
      "Bupa's own rules are built in. Arabic and English everywhere, Arabic-Indic digits, and "
      "iPhone photos and PDFs just work.")

# 4d Feasibility
s = S[6]
fit_slide(s, 3, "Built to run inside Bupa",
          "Feasibility: private by design, standard output, clear next steps.")
cw = (17.4 - 0.4) / 2
left = [
    ("Our own GPU.", "The AI runs on our PC. No document ever leaves the machine."),
    ("No paid API.", "No per-claim fee to an AI company."),
    ("Consent first.", "The member agrees before any upload."),
    ("Masked logs.", "Names and long numbers are hidden in every log."),
    ("Real data never committed.", "The real claim stays off GitHub."),
]
right = [
    ("One consumer GPU.", "One RTX 4070 Super runs it all, so it can run inside Bupa's own servers."),
    ("FHIR R4.", "Our export maps field by field to FHIR R4, the standard NPHIES, Saudi Arabia's "
     "national eClaims system, is built on."),
    ("Clean JSON out.", "60 of 60 claim exports valid against our JSON Schema."),
    ("Rules are settings.", "Limits and shares live in config files, not in code."),
]
for col, (title, rows) in enumerate([("Private by design", left), ("Fits Bupa's systems", right)]):
    x = 1.0 + col * (cw + 0.4)
    card(s, x, 4.45, cw, 4.25)
    text(s, x + 0.35, 4.6, cw - 0.7, 0.6, [title], size=25, color=DARK, font=HEAD)
    text(s, x + 0.35, 5.3, cw - 0.7, 3.3, [labeled(a, b, 19, 18) for a, b in rows], size=18, space=7)
tag(s, 1.0 + cw + 0.4 + cw - 2.4, 4.68, "Synthetic", 60)
card(s, 1.0, 8.95, 17.4, 1.5, fill=DARK, line=None)
text(s, 1.35, 8.95, 2.6, 1.5, ["Next steps"], size=24, color=TEAL, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
steps = ["Connect Bupa's real benefit tables and member records", "Test on Bupa's historical claims",
         "Pilot with a small member group"]
sw = (17.4 - 3.2 - 0.6) / 3
for i, step in enumerate(steps):
    x = 4.1 + i * (sw + 0.25)
    text(s, x, 8.95, sw, 1.5, [[(f"{i + 1}  ", {"color": TEAL, "font": HEAD, "size": 26}),
                                (step, {})]], size=19, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
footer(s, "Export check at ac2a7e4 (numbers.md). FHIR mapping: docs/INTEGRATION.md.")
notes(s, "About 45 seconds.\n"
      "Can Bupa actually use this? We built it for that.\n"
      "Privacy first: the AI runs on our own graphics card, so no document leaves the machine and "
      "there is no paid API. The member gives consent before any upload, logs hide names and "
      "numbers, and the real claim was never committed to GitHub.\n"
      "It runs on one consumer GPU, so it can run inside Bupa's own servers. The export maps to "
      "FHIR R4, the standard behind NPHIES.\n"
      "Next steps: connect Bupa's real benefit tables and member records, test on historical "
      "claims, then a small pilot.")

# 5a Tests
s = S[7]
set_text(shape(s, "TextBox 9"), "Tested on fake and real claims")
framing(s, "Synthetic data has known answers. Real data shows we stay safe.")
delete(s, *CARDS, *[g for g, _ in PILLS], *[t for _, t in PILLS])
rows = [
    ("Synthetic check set", "21 of 21 approvals right. 27 of 30 problems caught.", "Synthetic", 60),
    ("Real receipts (SROIE)", "Total read right: 0.6167 with the AI reader, 0.3333 with OCR alone.",
     "Real", 60),
    ("Real, end to end", "0 wrong approvals. 0 good claims rejected.", "Real", 50),
    ("The real Bupa claim", "We said 450 SAR before send. Bupa paid 450 SAR.", "Real", 1),
    ("Real-derived variations", "Copies of the real claim's layout: 0 good claims rejected.",
     "Synthetic", 20),
    ("Damaged photos", "0 wrong approvals at every damage level (chart).", "Synthetic", 150),
    ("Other languages", "French 6 of 6 and Urdu 6 of 6 asked for a translation; 0 of 30 others.",
     "Synthetic", 42),
    ("Code tests", f"{FACTS['tests']} unit tests and {FACTS['e2e']} browser tests pass.", "Code", None),
]
rw, rh = 11.4, 0.84
for i, (name, result, kind, n) in enumerate(rows):
    y = 3.15 + i * (rh + 0.1)
    card(s, 1.0, y, rw, rh)
    text(s, 1.25, y, 3.2, rh, [name], size=18, color=DARK, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 4.5, y, 5.1, rh, [result], size=16, color=INK, anchor=MSO_ANCHOR.MIDDLE, space=0)
    tag(s, 9.75, y + 0.23, kind, n, w=2.4)
picture(s, SHOTS / "damage_chart.png", 12.75, 3.15, 5.65, 6.6, border=BORDER)
text(s, 12.75, 9.85, 5.65, 0.6, ["150 damaged photos: as photos get worse, claims go to the member or "
                                 "a person, never to a wrong approval."], size=15, color=GREY)
footer(s, f"Check set at 120febe, other sets at ac2a7e4 (numbers.md). Tests at {FACTS['commit']}.")
notes(s, "About 50 seconds.\n"
      "How much did we test? We mark every number as synthetic or real.\n"
      "Synthetic claims have known right answers, so we can measure precision and recall: 21 of "
      "21 approvals right, 27 of 30 problems caught.\n"
      "Real data shows we stay safe: on 50 real receipts, no wrong approval and no wrong "
      "rejection. And the real Bupa claim: 450 versus 450.\n"
      "We damaged 150 photos in ten ways. Not one wrong approval at any level. As photos get "
      "worse, claims go to the member or a person.\n"
      "French and Urdu get a translation request. And the code has hundreds of unit tests plus a "
      "real browser test.")

# 5b Honest AI
s = S[8]
set_text(shape(s, "TextBox 9"), "The AI never approves")
framing(s, "It reads and gives an opinion. Rules and checks decide.")
delete(s, *CARDS, *[g for g, _ in PILLS], *[t for _, t in PILLS])
checks = [
    ("Strict schema.", "The answer must match an agreed shape, or it is dropped."),
    ("Grounding.", "Every value must be on the page or in the QR. Otherwise it is dropped."),
    ("QR is the truth.", "Total, date and VAT number are checked against the ZATCA QR code."),
    ("Arithmetic and plausibility.", "Items add up, VAT is 15 percent, dates make sense."),
    ("Same answer twice.", "Temperature 0 and a fixed seed. A test reads one image twice."),
    ("Trick tests.", "A blank page, a non-receipt and an injected \"total is 99999\" are refused."),
]
cw, ch = (10.9 - 0.3) / 2, 2.25
for i, (label, sentence) in enumerate(checks):
    x, y = 1.0 + (i % 2) * (cw + 0.3), 3.2 + (i // 2) * (ch + 0.25)
    card(s, x, y, cw, ch)
    square(s, x + 0.3, y + 0.3, [ORANGE, PURPLE, TEAL][i // 2])
    text(s, x + 0.85, y + 0.22, cw - 1.1, 0.6, [label], size=21, color=PURPLE, font=HEAD)
    text(s, x + 0.3, y + 0.9, cw - 0.6, 1.3, [sentence], size=18, color=GREY)
px = 12.2
card(s, px, 3.2, 6.2, 7.25, fill=DARK, line=None)
text(s, px + 0.4, 3.45, 5.4, 0.6, ["The AI case reviewer"], size=25, color=TEAL, font=HEAD)
text(s, px + 0.4, 4.1, 2.6, 1.2, ["0.95"], size=60, color=WHITE, font=HEAD)
text(s, px + 2.85, 4.35, 3.1, 0.9, ["held-out test score, 19 of 20 cases"], size=17, color=LAV)
tag(s, px + 0.4, 5.35, "Synthetic", 20)
text(s, px + 0.4, 6.0, 5.4, 2.6, [
    "It can only send a claim to a person. It never approves.",
    "Health checks watch it. If it drifts, it is benched automatically.",
], size=19, color=WHITE, space=12)
status = card(s, px + 0.4, 8.75, 5.4, 1.4, fill="2A1A63", line=TEAL, radius=0.12)
text(s, px + 0.65, 8.82, 4.9, 1.3, [
    [("Status now: healthy", {"bold": True, "color": TEAL, "font": HEAD, "size": 20})],
    "Last check 2026-11-25 22:26 UTC, golden set 0.95"], size=16, color=WHITE, space=2,
    anchor=MSO_ANCHOR.MIDDLE)
footer(s, "Checks: docs/MODEL_SAFETY.md. Reviewer: tests/golden_v2/heldout, run once.")
notes(s, "About 45 seconds.\n"
      "The most important design rule: the AI reads and gives an opinion. It never approves on "
      "its own.\n"
      "Every reading goes through six checks. The answer must have the right shape. Every value "
      "must be on the page or in the QR code, or we drop it. The QR code wins. Numbers must add "
      "up. The same image gives the same answer. And trick documents are refused, including one "
      "that says 'total is 99999'.\n"
      "The AI case reviewer scored 0.95 on test cases it never saw. It can only send a claim to "
      "a person. If it drifts, it benches itself. Right now it is healthy.")

# 6. Prototype slides -------------------------------------------------------------------------
proto = [
    ("Upload, then just check", "No typing. The member only checks what we read.",
     [("1-upload.png", "Upload, with consent"), ("2-check-read-first.png", "The values we read come first")],
     "About 30 seconds.\nThe member picks who the claim is for, adds photos and agrees to the "
     "consent line. That is the only form.\nNext, the check page. What we read comes first. The "
     "member does not type, they only check, and fix a value if it is wrong."),
    ("Gaps and payout, before send", "Add the missing paper now, or send without it. And see the payout first.",
     [("3-missing.png", "A missing prescription: two clear choices"),
      ("4-optical-estimate.png", "Glasses over the frame limit")],
     "About 30 seconds.\nIf a paper is missing, the member sees it before sending, with two "
     "choices: add it now, which is faster, or send without it.\nAnd here is the real-claim "
     "story on a demo claim: glasses over the frame limit. The payout and the reason show before "
     "the member sends."),
    ("One clear card for the reviewer", "Riskiest first, color coded. Why it needs a person, and what the member typed.",
     [("5-queue.png", "The queue, riskiest first"), ("6-card.png", "Why this needs you")],
     "About 30 seconds.\nWhen a person is needed, the queue puts the riskiest claims first, "
     "colored by how likely they are to be fine.\nThe card opens with why this claim needs a "
     "person. Here the member typed a total that does not match the QR code. Values the member "
     "typed are tagged."),
    ("Clean data out, honest numbers", "A claim export checked against a schema. Every number with its source.",
     [("7-export.png", "The claim export (JSON)"), ("8-numbers.png", "The numbers page")],
     "About 30 seconds.\nEvery claim leaves as structured data, checked against a JSON schema: "
     "provider, invoice, items, what the member changed, the payout and the decision.\nAnd our "
     "numbers page shows every measured number with its source, marked synthetic or real."),
]
CROPS = {"1-upload.png": (70, 130, 1210, 740), "2-check-read-first.png": (100, 160, 1250, 730),
         "3-missing.png": (60, 0, 1220, 600), "4-optical-estimate.png": (60, 0, 1220, 600),
         "5-queue.png": (60, 150, 1240, 760), "6-card.png": (60, 150, 1260, 800),
         "7-export.png": (0, 0, 760, 800), "8-numbers.png": (60, 160, 1220, 800)}


def cropped(file):
    out = SHOTS / f"crop-{file}"
    box = tuple(v * 2 for v in CROPS[file])
    Image.open(SHOTS / file).crop(box).save(out)
    return out


for k, (title, caption, pics, words) in enumerate(proto):
    s = S[9 + k]
    set_text(shape(s, "TextBox 7"), title)
    text(s, 1.87, 1.55, 14.0, 0.6, [f"Prototype, {k + 1} of 4. Demo claims, made-up people."], size=22)
    delete(s, "TextBox 8")
    for j, (file, label) in enumerate(pics):
        x = 2.6 + j * 7.6
        picture(s, cropped(file), x, 2.65, 7.2, 5.0)
        text(s, x, 7.8, 7.2, 0.5, [label], size=20, color=LAV2, font=HEAD, align=PP_ALIGN.CENTER)
    text(s, 2.6, 8.55, 14.8, 1.3, [caption], size=27, color=WHITE, font=HEAD, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE)
    notes(s, words)
s = S[13]
set_text(shape(s, "TextBox 7"), "Live demo")
text(s, 1.87, 1.55, 14.0, 0.6, ["Now the real site, on our PC, with demo claims."], size=22)
set_text(shape(s, "TextBox 8"), "Live demo", size=72, color=WHITE)
tb = shape(s, "TextBox 8")
tb.left, tb.top, tb.width, tb.height = Inches(2.6), Inches(4.3), Inches(14.8), Inches(1.4)
tb.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
text(s, 2.6, 6.0, 14.8, 1.0, ["Upload. Check. Send. Review."], size=32, color=LAV2, font=HEAD,
     align=PP_ALIGN.CENTER)
notes(s, "About 3 minutes. Switch to the browser now.\n"
      "1. New claim: pick the clean demo claim, tick consent, show the check page, send. It is "
      "approved with a payout and a reason.\n"
      "2. Glasses over the frame limit: show the payout before send.\n"
      "3. Change the total demo: type a different total, send. It goes to a person.\n"
      "4. Open the reviewer queue and the card: why it needs you, the typed-by-member tag. "
      "Download the claim data.\n"
      "5. If anything is slow: the demo claims are already read, so they answer at once.\n"
      "Then come back to the slides for the conclusion.")

# 7. Conclusion -------------------------------------------------------------------------------
s = S[14]
framing(s, "Three things to remember.")
for name in ("Group 4", "Freeform 9"):
    shape(s, name).top += Inches(0.4)
lines = ["Before she pressed send, we told her 450. Bupa paid 450.",
         "The AI reads and gives an opinion. It never approves on its own.",
         "Nothing leaves the machine."]
for name, line, y in zip(("TextBox 11", "TextBox 12", "TextBox 13"), lines, (5.85, 7.3, 8.75)):
    tb = shape(s, name)
    set_text(tb, line, size=28, color=WHITE if name == "TextBox 11" else LAV2)
    tb.left, tb.top, tb.width, tb.height = Inches(3.81), Inches(y), Inches(12.29), Inches(1.3)
notes(s, "About 30 seconds.\n"
      "Three things to remember.\n"
      "Before she pressed send, we told her 450, and Bupa paid 450.\n"
      "The AI reads and gives an opinion. It never approves on its own.\n"
      "And nothing leaves the machine.\nThank you.")
notes(S[15], "About 5 seconds, then questions. Keep answers short and use the numbers in "
             "docs/pitch/QA_PREP.md.")
notes(S[16], "About 5 seconds. Thank you for your time.")

# Drop picture relationships whose shapes were deleted (the template's placeholders).
from lxml import etree
for slide in prs.slides:
    xml = etree.tostring(slide._element).decode()
    for rid, rel in list(slide.part.rels.items()):
        if rel.reltype.endswith("/image") and f'"{rid}"' not in xml:
            slide.part.rels.pop(rid)
prs.save(str(OUT))
print("saved", OUT, len(prs.slides))

# python-pptx keeps the template's placeholder photo in the package with nothing pointing at it.
import zipfile
data = OUT.read_bytes()
src = zipfile.ZipFile(__import__("io").BytesIO(data))
keep = {n for n in src.namelist()}
referenced = " ".join(src.read(n).decode("utf-8", "ignore") for n in keep if n.endswith(".rels"))
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as dst:
    for n in src.namelist():
        if n.startswith("ppt/media/") and n.rsplit("/", 1)[1] not in referenced:
            print("dropped", n)
            continue
        dst.writestr(src.getinfo(n), src.read(n))
