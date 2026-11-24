"""Turn OCR text boxes from a receipt into fields and line items. Pure logic, no OCR here.

Fields are found by their label words in English or Arabic, never by a fixed position, so the
parser works on more than one layout. OCR misreads are expected: labels and service names are
matched with a similarity ratio, letter O inside numbers is fixed, and quantity is inferred
from amount and unit price when OCR misses it.
"""

import re
from difflib import SequenceMatcher
from statistics import mean

from reimbursement_council.config.models import OcrConfig, Settings
from reimbursement_council.core.models.claim import ExtractedField, LineItem, ReaderOutput
from reimbursement_council.core.models.common import FieldName, FieldSource, Model, Score
from reimbursement_council.core.text import digits_to_ascii, normalize_text

Box = tuple[int, int, int, int]
SOURCE: FieldSource = "ocr"

RAW_LABELS: dict[str, tuple[str, ...]] = {
    "vat_number": ("vat no", "vat number", "tax no", "tax number", "الرقم الضريبي", "رقم ضريبي"),
    "subtotal": (
        "subtotal",
        "sub total",
        "amount before vat",
        "net",
        "المجموع",
        "المجموع الفرعي",
        "المبلغ قبل الضريبة",
        "الصافي",
    ),
    "vat_total": (
        "vat",
        "vat 15",
        "vat amount",
        "tax",
        "tax 15",
        "ضريبة القيمة المضافة",
        "الضريبة",
        "مبلغ الضريبة",
    ),
    "total": ("total", "total sar", "grand total", "الإجمالي", "الإجمالي المستحق", "المجموع الكلي"),
    "date": ("date", "التاريخ"),
    "patient": ("patient", "customer", "المريض", "اسم المريض", "العميل"),
}
HEADER_WORDS = ("service", "qty", "price", "amount", "الخدمة", "الكمية", "السعر", "المبلغ")
LABELS = {
    field: tuple(tuple(normalize_text(label).split()) for label in labels)
    for field, labels in RAW_LABELS.items()
}
MONEY_ROWS = ("subtotal", "vat_total", "total")

_MONEY = re.compile(r"(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+)\.\s?(\d{2})(?![\d])")
_VAT_NUMBER = re.compile(r"(?<!\d)3\d{13}3(?!\d)")
_DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{1,2}):(\d{2}))?")
_DATE_DMY = re.compile(r"(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?")
_DIGITISH = re.compile(r"[0-9OoIl]{2,}")
_LONE_INT = re.compile(r"^\d{1,2}$")
_ARABIC = re.compile("[؀-ۿ]")
_LATIN = re.compile("[A-Za-z]")


class OcrLine(Model):
    """One text box from the OCR engine. box is x0, y0, x1, y1 in pixels."""

    text: str
    confidence: Score
    box: Box


def _center(line: OcrLine) -> float:
    return (line.box[1] + line.box[3]) / 2


def _height(line: OcrLine) -> int:
    return max(1, line.box[3] - line.box[1])


def group_rows(lines: list[OcrLine], overlap: float = 0.5) -> list[list[OcrLine]]:
    """Lines whose vertical centers are close form one row, sorted left to right."""
    rows: list[list[OcrLine]] = []
    for item in sorted(lines, key=_center):
        if rows:
            row = rows[-1]
            row_center = mean(_center(x) for x in row)
            limit = overlap * min(_height(item), min(_height(x) for x in row))
            if abs(_center(item) - row_center) <= limit:
                row.append(item)
                continue
        rows.append([item])
    return [sorted(row, key=lambda x: x.box[0]) for row in rows]


def _is_arabic(text: str) -> bool:
    return bool(_ARABIC.search(text)) and not _LATIN.search(text)


def _join(lines: list[OcrLine]) -> str:
    """Join text boxes in reading order: right to left when they are Arabic."""
    if lines and all(_is_arabic(x.text) for x in lines):
        lines = sorted(lines, key=lambda x: -x.box[0])
    return " ".join(x.text.strip() for x in lines)


def _fix_digits(text: str) -> tuple[str, bool]:
    """Letter O, I or l inside a number becomes 0 or 1. Returns the text and whether it changed."""

    def fix(match: re.Match[str]) -> str:
        token = match.group(0)
        if not any(char.isdigit() for char in token):
            return token
        return token.replace("O", "0").replace("o", "0").replace("I", "1").replace("l", "1")

    fixed = _DIGITISH.sub(fix, digits_to_ascii(text))
    return fixed, fixed != digits_to_ascii(text)


def _similar(a: str, b: str, ratio: float) -> bool:
    return a == b or SequenceMatcher(None, a, b).ratio() >= ratio


def _label_match(words: list[str], field: str, ratio: float) -> tuple[int, float]:
    """(word count, similarity) of the best label of this field found in the words, or (0, 0)."""
    best = (0, 0.0)
    for label in LABELS[field]:
        size = len(label)
        target = " ".join(label)
        for start in range(0, len(words) - size + 1):
            window = " ".join(words[start : start + size])
            score = 1.0 if window == target else SequenceMatcher(None, window, target).ratio()
            if score >= ratio:
                best = max(best, (size, score))
    return best


def _label_size(words: list[str], field: str, ratio: float) -> int:
    return _label_match(words, field, ratio)[0]


def _classify(row: list[OcrLine], cfg: OcrConfig) -> str | None:
    """The field whose longest, then closest, label is in the row."""
    words = normalize_text(_fix_digits(_join(row))[0]).split()
    scores = {field: _label_match(words, field, cfg.label_match_ratio) for field in LABELS}
    field, (size, _) = max(scores.items(), key=lambda pair: pair[1])
    return field if size else None


def _money_in(line: OcrLine) -> list[int]:
    text, _ = _fix_digits(line.text)
    return [int(whole.replace(",", "")) * 100 + int(cents) for whole, cents in _MONEY.findall(text)]


def _field(
    document_id: str, name: FieldName, value: str, text: str, confidence: float
) -> ExtractedField:
    return ExtractedField(
        document_id=document_id,
        name=name,
        value=value,
        original_text=text,
        source=SOURCE,
        confidence=max(0.0, min(1.0, confidence)),
    )


def _is_header(row: list[OcrLine], cfg: OcrConfig) -> bool:
    words = normalize_text(_join(row)).split()
    hits = {
        h
        for h in HEADER_WORDS
        for w in words
        if _similar(w, normalize_text(h), cfg.label_match_ratio)
    }
    return len(hits) >= 2


def _match_service(texts: list[str], settings: Settings) -> str | None:
    """The service whose longest alias has every word in the item text."""
    words = normalize_text(" ".join(_fix_digits(t)[0] for t in texts)).split()
    best: tuple[int, str] | None = None
    ratio = settings.decision.ocr.alias_match_ratio
    for code, price in settings.prices.items():
        for alias in price.aliases:
            alias_words = normalize_text(alias).split()
            found = alias_words and all(
                any(_similar(w, a, ratio) for w in words) for a in alias_words
            )
            if found and (best is None or len(alias_words) > best[0]):
                best = (len(alias_words), code)
    return None if best is None else best[1]


def _items(rows: list[list[OcrLine]], document_id: str, settings: Settings) -> list[LineItem]:
    cfg = settings.decision.ocr
    items: list[LineItem] = []
    texts: list[list[str]] = []
    for row in rows:
        money = [(m, line) for line in row for m in _money_in(line)]
        ints = [line for line in row if _LONE_INT.match(digits_to_ascii(line.text.strip()))]
        words = [line for line in row if not _money_in(line) and line not in ints]
        if not money:
            if items and words:
                texts[-1].append(_join(words))
            continue
        money.sort(key=lambda pair: pair[1].box[0])
        amount = money[-1][0]
        unit = money[-2][0] if len(money) >= 2 else amount
        if ints:
            quantity = int(digits_to_ascii(ints[0].text.strip()))
        elif unit and amount % unit == 0:
            quantity = amount // unit
        else:
            quantity = 1
        confidence = min(line.confidence for line in row)
        if quantity < 1 or quantity * unit != amount:
            confidence *= cfg.pattern_miss_factor
            quantity = max(quantity, 1)
        description = _join(words) if words else "item"
        items.append(
            LineItem(
                description=description,
                service_code=None,
                quantity=quantity,
                unit_price=unit,
                amount=amount,
                confidence=confidence,
            )
        )
        texts.append([description])
    matched = []
    for item, item_texts in zip(items, texts, strict=True):
        english = next((t for t in item_texts if _LATIN.search(t)), item.description)
        matched.append(
            item.model_copy(
                update={
                    "service_code": _match_service(item_texts, settings),
                    "description": english,
                }
            )
        )
    return matched


def _date_fields(document_id: str, row_text: str, confidence: float) -> list[ExtractedField]:
    text, _ = _fix_digits(row_text)
    iso = _DATE_ISO.search(text)
    dmy = _DATE_DMY.search(text)
    if iso:
        year, month, day, hour, minute = iso.groups()
    elif dmy:
        day, month, year, hour, minute = dmy.groups()
    else:
        return []
    date_text = f"{year}-{month}-{day}"
    fields = [_field(document_id, "treatment_date", date_text, row_text, confidence)]
    if hour and minute:
        stamp = f"{date_text}T{int(hour):02d}:{minute}:00"
        fields.append(_field(document_id, "invoice_timestamp", stamp, row_text, confidence))
    return fields


def parse_receipt_lines(document_id: str, lines: list[OcrLine], settings: Settings) -> ReaderOutput:
    cfg = settings.decision.ocr
    rows = group_rows(lines, cfg.row_overlap)
    kinds = [_classify(row, cfg) for row in rows]
    fields: list[ExtractedField] = []
    found: set[str] = set()

    for row in rows:  # VAT number: a 15 digit run that starts and ends with 3
        for line in row:
            text, fixed = _fix_digits(line.text.replace(" ", ""))
            match = _VAT_NUMBER.search(text)
            if match and "vat_number" not in found:
                factor = cfg.pattern_miss_factor if fixed else 1.0
                fields.append(
                    _field(
                        document_id,
                        "vat_number",
                        match.group(0),
                        line.text,
                        line.confidence * factor,
                    )
                )
                found.add("vat_number")

    for row, kind in zip(rows, kinds, strict=True):
        if kind in MONEY_ROWS and kind not in found:
            money = [(m, line) for line in row for m in _money_in(line)]
            if money:
                value, line = money[0]
                fields.append(_field(document_id, kind, str(value), line.text, line.confidence))  # type: ignore[arg-type]
                found.add(kind)
        if "treatment_date" not in found:
            dated = _date_fields(document_id, _join(row), min(x.confidence for x in row))
            if dated:
                fields.extend(dated)
                found.add("treatment_date")
        if kind == "patient" and "patient_name" not in found:
            label_free = [
                x
                for x in row
                if not _label_size(normalize_text(x.text).split(), "patient", cfg.label_match_ratio)
            ]
            if label_free:
                name = _join(label_free)
                fields.append(
                    _field(
                        document_id,
                        "patient_name",
                        name,
                        name,
                        min(x.confidence for x in label_free),
                    )
                )
                found.add("patient_name")

    anchor = next((i for i, kind in enumerate(kinds) if kind), len(rows))
    top = rows[: min(anchor, 3)]
    if top:
        named = next((row for row in top if any(_LATIN.search(x.text) for x in row)), top[0])
        name = _join(named)
        confidence = mean(x.confidence for x in named) * cfg.heuristic_factor
        fields.append(_field(document_id, "provider_name", name, name, confidence))

    header = next((i for i, row in enumerate(rows) if _is_header(row, cfg)), None)
    items: list[LineItem] = []
    if header is not None:
        end = next((i for i in range(header + 1, len(rows)) if kinds[i] in MONEY_ROWS), len(rows))
        items = _items(rows[header + 1 : end], document_id, settings)
    return ReaderOutput(fields=fields, line_items=items, qr_payloads=[])
