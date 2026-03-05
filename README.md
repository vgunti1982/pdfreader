# PDF Redact Tool

A CLI tool to permanently delete/redact specific content from PDFs — text, regex patterns, pages, regions, and images.

---

## Setup

### 1. Create Virtual Environment

```bash
python3 -m venv .venv
```

### 2. Activate

```bash
# Linux / macOS
source .venv/bin/activate

# Windows (CMD)
.venv\Scripts\activate.bat

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install pymupdf
```

---

## Usage

### Redact keywords
```bash
python pdf_redact.py -i input.pdf -o output.pdf --text "Confidential" "John Doe"
```

### Redact via regex (e.g. SSNs)
```bash
python pdf_redact.py -i input.pdf -o output.pdf --regex "\d{3}-\d{2}-\d{4}"
```

### Delete pages (1-indexed)
```bash
python pdf_redact.py -i input.pdf -o output.pdf --delete-pages 2 5 7
```

### Redact a rectangular region (x0 y0 x1 y1 in PDF points)
```bash
python pdf_redact.py -i input.pdf -o output.pdf --region 0 750 600 800
```

### Remove all images
```bash
python pdf_redact.py -i input.pdf -o output.pdf --remove-images
```

### Chain multiple operations
```bash
python pdf_redact.py -i input.pdf -o output.pdf \
  --text "SECRET" \
  --regex "\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b" \
  --delete-pages 1 \
  --remove-images
```

---

## Deactivate Environment

```bash
deactivate
```
