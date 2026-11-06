# Invoice batch to CSV

A local invoice-review application: turn supplier PDFs and invoice photos into an editable table, then export pre-tax amounts to CSV. It replaces repeated transcription of invoice dates and totals, not accounting review.

The interface is in French. The desktop launcher targets macOS and wraps Flask + JavaScript in a pywebview window. Extraction uses local PDF text, Tesseract OCR and supplier-specific YAML/regex rules. **There is no LLM or cloud extraction API** ([decision](docs/adr/0001-pas-de-llm-pour-extraction.md)); this is an automation project, not an AI agent.

## What it does

1. Drop a batch of files: **one file = one invoice or credit note = one row**, including multi-page PDFs.
2. Extract text and match supplier templates; prefill issuer, date and pre-tax amount (`HT`, *hors taxes*).
3. Preview the document and correct issuer, date, amount or invoice/credit-note type.
4. Review net totals by issuer and download either detailed or grouped CSV.

### Supported inputs and extraction limits

| Input | Actual extraction path |
| --- | --- |
| `.pdf` (case-insensitive) | pdfplumber reads all pages. At least 50 native-text characters across the document, after trimming leading/trailing whitespace, keeps the native path. |
| PDF below that threshold, including scans | Poppler renders pages at 200 DPI; Tesseract reads them using French (`fra`). |
| `.jpg`, `.jpeg`, `.png`, `.heic` | Pillow opens the image, converts it to RGB and passes it to Tesseract. HEIC requires pillow-heif. |

The threshold is a document-level heuristic, not a quality check: a mixed PDF with enough native text will not OCR its image-only pages. OCR depends on installed native tools and scan quality; it is not guaranteed to recover every field.

Exactly one matching supplier template supplies a **fixed issuer name** and regex rules for date and HT amount. With no match, or multiple matches, generic rules may prefill date/HT but never infer an issuer. Such rows require review. New suppliers/layout changes need YAML maintenance; manual edits do not train or change templates.

`OK` means the pipeline's checks passed, **not that the invoice is certified correct**. OCR, missing/invalid fields and unknown/ambiguous templates initially produce `A_VERIFIER` (shown as “À vérifier”). Export remains possible after the UI's warning; inspect those rows first.

Credit-note markers in text or filenames produce `AVOIR`, otherwise the default is `FACTURE`. Credit amounts are negative and reduce issuer totals. The tool does not split combined invoices, join files into one invoice, calculate HT from tax-inclusive totals, or handle rent receipts as supported supplier invoices.

## Output

Both exports use UTF-8 with BOM, semicolons and decimal commas for French spreadsheet settings. Dates are normalized to `DD/MM/YYYY` when valid.

- **Exporter détail** (`lot-detail.csv`): one row per document, invoices before credit notes. Columns: `fichier;emetteur;date;montant_ht;statut;type`.
- **Exporter groupé** (`lot-groupe.csv`): `emetteur;montant_ht;nb_documents;fichier;date;statut;type`. Named issuers are aggregated; documents without an issuer remain individual detail rows. Aggregated rows leave document/date/status/type blank. Missing amounts contribute zero to totals, so a grouped total is not proof that all amounts were extracted.

Diagnostic reasons appear in the UI, not as a CSV column. The downloadable diagnostic journal can contain filenames and extracted financial fields: treat it as sensitive too.

## Run locally

### macOS desktop

For a packaged build, see [GitHub Releases](https://github.com/Ant3xes/pdf-to-csv/releases). The repository's [build guide](docs/build-macos-release.md) describes an unsigned `.app`/`.dmg`; availability and compatibility of a particular release should be checked on its release page. Do not bypass operating-system warnings for an artifact you do not trust.

From a checkout, use Python 3 with `venv`/pip support and Homebrew. No exact Python minimum or locked dependency set is declared in this repository. A headless Linux check of the documentation used Python 3.14; that does not certify the macOS GUI on that version.

```bash
brew install tesseract tesseract-lang poppler libheif
tesseract --version
tesseract --list-langs  # must include fra
pdftoppm -v

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.launcher
```

Run the Python commands from the repository root. The launcher binds to `127.0.0.1` on an available port and opens a native window. Other operating systems need their own Tesseract/Poppler installation and a compatible pywebview GUI backend; macOS packaging instructions are not a cross-platform installer.

There is no database or saved session/history. Uploaded working copies are written to a temporary directory and removed in the request's cleanup path. The journal lives in server memory until reset or exit; exported CSV/journal files remain wherever you save them. Local processing is not a security audit or a guarantee that operating-system temporary files can never remain after a crash. Do not expose the local server as a public service.

## Reproduce a safe example

After installing the Python requirements, run this from the repository root. **Everything below is synthetic**: it creates a minimal text PDF and an isolated demo template in a new temporary directory, then exercises the real extraction and CSV functions. It does not read bundled invoice documents, need OCR, or modify the application's supplier templates. Keep the printed directory if you want to inspect the generated PDF.

```bash
python - <<'PY'
from pathlib import Path
import tempfile
from app.lot import process_lot
from app.csv_export import export_csv

root = Path(tempfile.mkdtemp(prefix="synthetic-invoice-"))
templates = root / "templates"
templates.mkdir()
(templates / "demo.yml").write_text(r"""issuer: Synthetic Demo
keywords:
  - SYNTHETIC DEMO ONLY
fields:
  date: 'Date: (\d{2}/\d{2}/\d{4})'
  amount: 'Total HT: (\d+,\d{2})'
options:
  date_formats: ['%d/%m/%Y']
  decimal_separator: ','
""", encoding="utf-8")
stream = (b"BT /F1 12 Tf 50 750 Td "
          b"(SYNTHETIC DEMO ONLY - no real invoice) Tj 0 -20 Td "
          b"(Date: 01/01/2026) Tj 0 -20 Td (Total HT: 12,50) Tj ET")
objects = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
    b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
]
data = bytearray(b"%PDF-1.4\n")
offsets = [0]
for number, obj in enumerate(objects, 1):
    offsets.append(len(data))
    data.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
xref = len(data)
data.extend(b"xref\n0 6\n0000000000 65535 f \n")
for offset in offsets[1:]:
    data.extend(f"{offset:010d} 00000 n \n".encode())
data.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
pdf = root / "synthetic-demo.pdf"
pdf.write_bytes(data)
print(export_csv(process_lot([pdf], templates)).lstrip("\ufeff"), end="")
print(f"Synthetic files: {root}")
PY
```

CSV output from this example (the final temporary path varies):

```csv
fichier;emetteur;date;montant_ht;statut;type
synthetic-demo.pdf;Synthetic Demo;01/01/2026;12,50;OK;FACTURE
```

This proves only the controlled native-text/template/export path, not arbitrary supplier accuracy, OCR, GUI operation or production readiness. Do not use real invoices or rent receipts for public demos, screenshots or bug reports.

## Architecture and maintenance

```text
PDF/images -> native text or local OCR -> template detection
           -> field normalization + review status -> editable UI -> CSV
```

| Module | Responsibility |
| --- | --- |
| `app/extraction.py` | Supported suffixes, native PDF text and OCR fallback |
| `app/templates_loader.py`, `invoice_templates/` | YAML loading, supplier matching and field regexes |
| `app/lot.py`, `app/normalisation.py`, `app/amounts.py` | Batch processing, fallback rules, dates, amounts and credit-note classification |
| `app/web.py`, `app/static/`, `app/templates/` | Local Flask API, preview and editable JavaScript UI |
| `app/csv_export.py`, `app/export_agrege.py` | Detailed CSV and issuer aggregation |
| `app/launcher.py`, `app/desktop_api.py` | Local server lifecycle, native window and desktop file dialogs |
| `packaging/`, `scripts/` | PyInstaller build and native-tool staging for macOS |

Business vocabulary: [CONTEXT.md](CONTEXT.md). Decisions: [no LLM](docs/adr/0001-pas-de-llm-pour-extraction.md), [Flask/JS UI](docs/adr/0002-interface-flask-js.md), [HT amounts](docs/adr/0003-montant-ht.md), [grouped export](docs/adr/0004-export-agrege-par-emetteur.md), [detailed export/status](docs/adr/0005-export-detail-avec-statut.md). These domain/architecture documents are in French.

### Tests

Requirements include pytest and Playwright. A corpus-independent subset exercises in-memory export behavior and launcher/runtime helpers without the private corpus:

```bash
python -m pytest tests/test_csv_export.py tests/test_export_agrege.py tests/test_launcher.py tests/test_runtime_paths.py
```

The complete suite is `python -m pytest`; **some tests read a private corpus of real invoices (`private_corpus/`, `private_corpus_2/`) that is not provided with this repository and is git-ignored**; they are skipped automatically when it is absent, and UI tests require a Playwright browser (`python -m playwright install chromium`). OCR cases also require native tools and `fra`. Do not reproduce the financial contents of the private corpus in reports. The full suite, OCR and macOS packaging were not executed for this documentation update. No dedicated documentation linter or CI workflow is configured in the checkout.

For release maintenance, follow the [macOS build guide](docs/build-macos-release.md) and install `requirements-build.txt` in addition to runtime requirements. No build or deployment is needed to try the synthetic example.

## Project status and attribution

This repository is maintained under [Ant3xes](https://github.com/Ant3xes). It contains a local single-user application and release tooling, not evidence of a deployed client service or a measured extraction-accuracy guarantee.

The repository documents the local/no-LLM design. It does **not** establish a verified breakdown of Romain Pereira's historical design, implementation, supervision and testing work versus AI assistance. No exclusive-authorship claim or percentage is inferred from commit identities or agent instructions. This README update was AI-assisted and checked against the source and the synthetic example; that statement does not establish how the application was originally built.

Agent/issue conventions: [AGENTS.md](AGENTS.md) and [issue tracker](docs/agents/issue-tracker.md).
