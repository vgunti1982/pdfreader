"""
pdf_redact.py — Delete/redact specific content from PDFs using PyMuPDF.

Supports:
  - Text redaction by keyword or regex
  - Page deletion
  - Region-based redaction (bounding box)
  - Image removal

Install:
  pip install pymupdf

Usage:
  python pdf_redact.py --input input.pdf --output output.pdf --text "Confidential" "SSN"
  python pdf_redact.py --input input.pdf --output output.pdf --regex r"\d{3}-\d{2}-\d{4}"
  python pdf_redact.py --input input.pdf --output output.pdf --delete-pages 2 4 5
  python pdf_redact.py --input input.pdf --output output.pdf --region 0 50 200 100 50 200
"""

import argparse
import re
import sys
import logging
from pathlib import Path

import fitz  # PyMuPDF


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Core redaction functions
# ─────────────────────────────────────────────

def redact_text(doc: fitz.Document, keywords: list[str], case_sensitive: bool = False) -> int:
    """
    Permanently redact all occurrences of given keywords/phrases.
    Returns total redaction count.
    """
    count = 0
    flags = 0 if case_sensitive else fitz.TEXT_INHIBIT_SPACES

    for page_num, page in enumerate(doc):
        for keyword in keywords:
            quads = page.search_for(keyword, quads=True)
            for quad in quads:
                page.add_redact_annot(quad, fill=(0, 0, 0))  # black fill
                count += 1
                log.debug(f"Page {page_num + 1}: marked '{keyword}' for redaction")

        if page.annots(types=[fitz.PDF_ANNOT_REDACT]):
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    return count


def redact_regex(doc: fitz.Document, pattern: str, flags: int = re.IGNORECASE) -> int:
    """
    Redact all text matching a regex pattern across all pages.
    Returns total redaction count.
    """
    compiled = re.compile(pattern, flags)
    count = 0

    for page_num, page in enumerate(doc):
        # Extract words with their bounding boxes
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        page_text = page.get_text("text")

        # Find all matches in the raw text, then locate them on the page
        matches = list(compiled.finditer(page_text))
        if not matches:
            continue

        for match in matches:
            match_text = match.group()
            hit_quads = page.search_for(match_text, quads=True)
            for quad in hit_quads:
                page.add_redact_annot(quad, fill=(0, 0, 0))
                count += 1
                log.debug(f"Page {page_num + 1}: regex match '{match_text}' marked")

        if page.annots(types=[fitz.PDF_ANNOT_REDACT]):
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    return count


def delete_pages(doc: fitz.Document, page_numbers: list[int]) -> int:
    """
    Delete specific pages (1-indexed). Operates in reverse to preserve indices.
    Returns count of deleted pages.
    """
    valid = [p - 1 for p in page_numbers if 1 <= p <= len(doc)]
    invalid = [p for p in page_numbers if p < 1 or p > len(doc)]

    if invalid:
        log.warning(f"Skipping out-of-range pages: {invalid} (doc has {len(doc)} pages)")

    if valid:
        doc.delete_pages(sorted(set(valid), reverse=True))
        log.info(f"Deleted pages: {sorted(set(p + 1 for p in valid))}")

    return len(valid)


def redact_region(doc: fitz.Document, regions: list[tuple], page_numbers: list[int] | None = None) -> int:
    """
    Redact a rectangular region on specified pages (or all pages if None).
    regions: list of (x0, y0, x1, y1) tuples in PDF point units (1 pt = 1/72 inch)
    page_numbers: 1-indexed list; None = all pages
    """
    count = 0
    target_pages = (
        [p - 1 for p in page_numbers if 1 <= p <= len(doc)]
        if page_numbers else range(len(doc))
    )

    for page_idx in target_pages:
        page = doc[page_idx]
        for rect_coords in regions:
            rect = fitz.Rect(*rect_coords)
            page.add_redact_annot(rect, fill=(0, 0, 0))
            count += 1

        if page.annots(types=[fitz.PDF_ANNOT_REDACT]):
            page.apply_redactions()

    return count


def remove_images(doc: fitz.Document, page_numbers: list[int] | None = None) -> int:
    """
    Remove all images from specified pages (or all pages).
    """
    count = 0
    target_pages = (
        [p - 1 for p in page_numbers if 1 <= p <= len(doc)]
        if page_numbers else range(len(doc))
    )

    for page_idx in target_pages:
        page = doc[page_idx]
        image_list = page.get_images(full=True)
        for img in image_list:
            xref = img[0]
            rect = page.get_image_rects(xref)
            for r in rect:
                page.add_redact_annot(r, fill=(1, 1, 1))  # white fill
                count += 1

        if page.annots(types=[fitz.PDF_ANNOT_REDACT]):
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)

    return count


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Redact/delete content from PDFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", "-i", required=True, help="Input PDF path")
    parser.add_argument("--output", "-o", required=True, help="Output PDF path")
    parser.add_argument("--text", nargs="+", metavar="KEYWORD", help="Keywords to redact")
    parser.add_argument("--regex", metavar="PATTERN", help="Regex pattern to redact")
    parser.add_argument("--delete-pages", nargs="+", type=int, metavar="PAGE", help="1-indexed page numbers to delete")
    parser.add_argument(
        "--region", nargs="+", type=float, metavar="COORD",
        help="Redact rectangular regions: x0 y0 x1 y1 [x0 y0 x1 y1 ...] (PDF points)"
    )
    parser.add_argument("--region-pages", nargs="+", type=int, metavar="PAGE", help="Pages to apply region redaction (default: all)")
    parser.add_argument("--remove-images", action="store_true", help="Remove all images")
    parser.add_argument("--case-sensitive", action="store_true", help="Case-sensitive text search")
    return parser.parse_args()


def main():
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        log.error(f"Input file not found: {input_path}")
        sys.exit(1)

    log.info(f"Opening: {input_path}")
    doc = fitz.open(str(input_path))
    total_ops = 0

    # 1. Page deletion (do first to reduce scope)
    if args.delete_pages:
        n = delete_pages(doc, args.delete_pages)
        total_ops += n
        log.info(f"Deleted {n} page(s)")

    # 2. Text keyword redaction
    if args.text:
        n = redact_text(doc, args.text, case_sensitive=args.case_sensitive)
        total_ops += n
        log.info(f"Redacted {n} text occurrence(s)")

    # 3. Regex redaction
    if args.regex:
        n = redact_regex(doc, args.regex)
        total_ops += n
        log.info(f"Redacted {n} regex match(es)")

    # 4. Region redaction
    if args.region:
        coords = args.region
        if len(coords) % 4 != 0:
            log.error("--region requires groups of 4 values: x0 y0 x1 y1")
            sys.exit(1)
        regions = [tuple(coords[i:i+4]) for i in range(0, len(coords), 4)]
        n = redact_region(doc, regions, page_numbers=args.region_pages)
        total_ops += n
        log.info(f"Applied {n} region redaction(s)")

    # 5. Image removal
    if args.remove_images:
        n = remove_images(doc)
        total_ops += n
        log.info(f"Removed {n} image(s)")

    if total_ops == 0:
        log.warning("No operations performed. Specify at least one action.")
        sys.exit(0)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path), garbage=4, deflate=True, clean=True)
    doc.close()

    log.info(f"Saved redacted PDF → {output_path}")
    log.info(f"Total operations: {total_ops}")


if __name__ == "__main__":
    main()
