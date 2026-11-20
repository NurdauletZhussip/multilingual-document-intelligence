# Invoice Lens

Ask an invoice question in Kazakh, Russian or English and get the value alongside the source line and page. An accounts-payable reviewer can compare translated copies before approving a payment.

The example concerns invoice **ALM-2048**. The Russian and Kazakh copies agree on **280,000 KZT**. An English revision adds a handling fee and asks for **285,000 KZT**. Asking one question across the three copies returns both amounts with their evidence.

## Try the discrepancy

From the repository directory, using Python 3.10 or newer:

```sh
python -m pip install .
python -m invoice_lens ask "Қанша төлеу керек?" examples/invoice-kk.txt examples/invoice-ru.txt examples/invoice-en-revision.pdf
```

The result includes these lines (spacing shortened):

```text
conflict (total)
280000.00 KZT
  invoice-kk.txt, p. 2, line 4 | Жалпы сома: 280 000,00 ₸
  invoice-ru.txt, p. 2, line 4 | Всего к оплате: 280 000,00 тенге
285000.00 KZT
  invoice-en-revision.pdf, p. 2, line 22 | Amount payable   KZT 285,000.00
```

[Inspect the English PDF](examples/invoice-en-revision.pdf) or read the [Kazakh](examples/invoice-kk.txt) and [Russian](examples/invoice-ru.txt) copies. All examples contain fictional data.

## Use your documents

```sh
python -m invoice_lens ask "Когда истекает срок платежа?" examples/invoice-en-revision.pdf
python -m invoice_lens extract examples/invoice-kk.txt --json
```

Supply one invoice at a time or copies with the same invoice number. Supported fields are the amount payable, payment deadline, supplier and invoice number. Extracted values include their filename, physical PDF page, line within extracted text, original wording and extraction method. UTF-8 text files can mark page breaks with a form feed. JSON output distinguishes a missing field, unsupported question, conflicting values and files that need to be reviewed separately.

For scans, install [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html) and the Kazakh, Russian and English language packs. Add the optional Python dependencies and enable OCR explicitly:

```sh
python -m pip install ".[ocr]"
tesseract --list-langs
python -m invoice_lens extract local-documents/scanned-invoice.pdf --ocr --languages kaz+rus+eng
```

OCR reads PNG/JPEG files and PDF pages with an empty text layer. A partially populated or garbled text layer can require manual review. All inference runs on your computer.

## How it works

1. Read the text on each page, preserving layout where the PDF provides it. Identify label/value rows separated by a colon, a tab or a gap of at least two spaces.
2. Fit a compact supervised classifier from the bundled [multilingual training phrases](invoice_lens/training.json). It represents text using word and character n-gram TF-IDF features and learns field scores with regularized least squares. Both questions and labels map to a common field across languages. Low scores, small margins and a background class trigger abstention.
3. Parse supported numeric amounts and dates into comparable values. Before comparing files, check that their invoice identifiers agree. Group equal values, preserve every citation and surface each distinct value for review.

This version handles flat label/value layouts. Supplier names and identifiers use exact comparison after whitespace normalization. Amounts need an explicit supported currency (KZT, RUB, EUR or USD) and a nonnegative value. Dates use ISO or dotted day-month-year format. Free-form narratives, itemized table reconstruction, multi-invoice bundles and general-purpose translation are outside the supported task.

## Reproduce the evaluation

```sh
python -m evaluation
python -m unittest discover -s tests -v
```

The [evaluation set](evaluation/cases.json) pairs 12 separately worded questions with three fictional two-page invoices. Each language pairing has four questions. The scorer checks the answer, filename, page and quoted source line.

| Local benchmark | Result |
|---|---:|
| Expected fields recovered | 12 of 12 |
| Returned field instances correct | 12 of 12 |
| Questions with the exact value and supporting citation | 36 of 36 |
| Unsupported questions rejected | 9 of 9 (3 distinct prompts) |

These figures cover a small, hand-authored text benchmark. The integration suite also checks native PDF extraction, disagreement across revisions, missing values, unrelated invoices and empty pages. An additional OCR integration test runs when Tesseract and the OCR dependencies are installed. Accuracy on production scans and unfamiliar templates remains unmeasured.
