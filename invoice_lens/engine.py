"""Extract fields and reconcile evidence across copies of the same invoice."""

import re
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal

from .ingest import read_pages

CURRENCIES = {"₸": "KZT", "тг": "KZT", "тенге": "KZT", "₽": "RUB", "руб": "RUB",
              "руб.": "RUB", "€": "EUR", "KZT": "KZT", "RUB": "RUB", "EUR": "EUR", "USD": "USD"}
CODES = {alias.casefold(): code for alias, code in CURRENCIES.items()}
CURRENCY = "|".join(map(re.escape, sorted(CODES, key=len, reverse=True)))
NUMBER = r"(?:\d{1,3}(?:[ ,]\d{3})+|\d+)(?:[.,]\d{2})?"
MONEY = re.compile(rf"(?:(?P<pre>{CURRENCY})\s*(?P<left>{NUMBER})|(?P<right>{NUMBER})\s*(?P<post>{CURRENCY}))", re.I)


@dataclass(frozen=True)
class Evidence:
    source: str
    page: int
    line: int
    quote: str
    method: str
    field: str
    value: str


def canonical(field, raw):
    value = " ".join(unicodedata.normalize("NFKC", raw).strip().split())
    if field == "invoice_id":
        return value if re.fullmatch(r"[\w][\w./-]{0,79}", value) else None
    if field == "due_date":
        for pattern in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(value, pattern).date().isoformat()
            except ValueError:
                continue
        return None
    if field == "total":
        match = MONEY.fullmatch(value)
        if not match:
            return None
        number = (match["left"] or match["right"]).replace(" ", "")
        if re.search(r",\d{2}$", number):
            number = number[:-3].replace(",", "") + "." + number[-2:]
        else:
            number = number.replace(",", "")
        currency = CODES[(match["pre"] or match["post"]).casefold()]
        return f"{Decimal(number):.2f} {currency}"
    return value or None


def extract(paths, model, ocr=False, languages="kaz+rus+eng"):
    facts, warnings = [], []
    if len({path.name for path in paths}) != len(paths):
        raise ValueError("Choose files with distinct filenames so citations are unambiguous.")
    for path in paths:
        for page, (text, method) in enumerate(read_pages(path, ocr, languages), start=1):
            if not text.strip():
                warnings.append(f"{path.name}, page {page}: no readable text. Check this page or retry with OCR.")
            for line, quote in enumerate(text.splitlines(), start=1):
                stripped = quote.strip()
                parts = re.split(r"\s*[:：]\s*|\t+| {2,}", stripped, maxsplit=1)
                if len(parts) != 2 or not parts[0] or not parts[1]:
                    continue
                field = model.classify(parts[0], min_similarity=0.32)
                if field is None:
                    continue
                value = canonical(field, parts[1])
                if value is None:
                    if field in {"total", "due_date"}:
                        warnings.append(f"{path.name}, page {page}, line {line}: check the format of {field}.")
                    continue
                facts.append(Evidence(path.name, page, line, stripped, method, field, value))
    return facts, warnings


def ask(question, model, facts, sources):
    field = model.classify(question)
    if field is None:
        return {"status": "unsupported_question", "field": None, "answers": []}
    if len(sources) > 1:
        ids = defaultdict(set)
        for fact in facts:
            if fact.field == "invoice_id":
                ids[fact.source].add(fact.value)
        all_ids = set().union(*ids.values())
        if len(all_ids) != 1 or any(not ids[source] for source in sources):
            return {"status": "select_one_invoice", "field": field, "answers": [],
                    "invoice_ids": {source: sorted(ids[source]) for source in sources}}
    grouped = defaultdict(list)
    for fact in facts:
        if fact.field == field:
            grouped[fact.value].append(asdict(fact))
    answers = [{"value": value, "citations": citations} for value, citations in grouped.items()]
    status = "missing" if not answers else "answered" if len(answers) == 1 else "conflict"
    return {"status": status, "field": field, "answers": answers}
