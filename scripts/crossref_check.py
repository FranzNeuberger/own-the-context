#!/usr/bin/env python3
"""Look up a DOI at Crossref and, optionally, compare it with an entry.

Use this for metadata stubs without a PDF, where details would otherwise be
copied from secondary citations. Crossref can flag a discrepancy; when a PDF
is at hand, its front matter decides, not the registry.

Usage:
  crossref_check.py DOI [--entry PATH] [--json]

  DOI       e.g. 10.1234/abcd.5678 or https://doi.org/10.1234/abcd.5678
  --entry   summary file whose metadata table is compared field by field
            (Year, Source pages, Title, first author). Pages are compared
            as normalised ranges: dash variants, "p."/"pp." and spaces are
            ignored, and an abbreviated last page ("101-12") counts as the
            full one ("101-112").

Set CROSSREF_MAILTO to your own contact address to use Crossref's polite
pool; nothing is sent otherwise beyond the DOI itself.

Exit code: 0 if found (and, with --entry, no discrepancy), 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vaultlib as vl  # noqa: E402

API = "https://api.crossref.org/works/"


def fetch(doi: str) -> dict | None:
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi.strip(), flags=re.I)
    url = API + urllib.parse.quote(doi)
    mailto = os.environ.get("CROSSREF_MAILTO")
    if mailto:
        url += "?" + urllib.parse.urlencode({"mailto": mailto})
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)["message"]
    except urllib.error.HTTPError as exc:
        print(f"Crossref: HTTP {exc.code} for {doi}")
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Crossref: network error ({exc})")
    return None


def summarise(msg: dict) -> dict:
    year = None
    for key in ("published-print", "issued", "published-online"):
        parts = (msg.get(key) or {}).get("date-parts") or [[None]]
        if parts[0] and parts[0][0]:
            year = parts[0][0]
            break
    authors = [
        f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
        for a in msg.get("author", [])
    ]
    return {
        "title": " ".join(msg.get("title") or []),
        "authors": authors,
        "year": year,
        "container": " ".join(msg.get("container-title") or []),
        "volume": msg.get("volume"),
        "issue": msg.get("issue"),
        "pages": msg.get("page"),
        "type": msg.get("type"),
        "doi": msg.get("DOI"),
    }


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


# Page ranges. Dashes of every kind count as a hyphen; "p."/"pp." prefixes
# and spaces are ignored; an abbreviated last page ("101-12") is expanded
# with the leading digits of the first page ("101-112"). A page may carry a
# letter prefix (e.g. "S12", "e1034"); both ends must then share it.
DASHES = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
PAGE = r"[A-Za-z]?\d+"
RANGE_RE = re.compile(r"(?<![\w.(])(?:pp?\.\s*)?(" + PAGE + r")\s*-\s*(" + PAGE + r")(?![\w(])")
SINGLE_RE = re.compile(r"(?<![\w.(\-])(?:pp?\.\s*)?(" + PAGE + r")(?![\w(\-])")


def _dash(s: str) -> str:
    return "".join("-" if c in DASHES else c for c in s or "")


def _split(page: str) -> tuple[str, int]:
    m = re.fullmatch(r"([A-Za-z]?)(\d+)", page)
    return m.group(1).lower(), int(m.group(2))


def page_range(first: str, last: str | None = None) -> tuple[str, int, int] | None:
    """Normalise one page or range to (prefix, first, last); None if invalid."""
    pre1, a = _split(first)
    if last is None:
        return pre1, a, a
    pre2, b = _split(last)
    digits_last = re.sub(r"\D", "", last)
    digits_first = str(a)
    if b < a and len(digits_last) < len(digits_first) and pre2 in ("", pre1):
        b = int(digits_first[: len(digits_first) - len(digits_last)] + digits_last)
        pre2 = pre1
    if pre2 not in ("", pre1) or b < a:
        return None
    return pre1, a, b


def parse_pages(s: str) -> tuple[str, int, int] | None:
    """Parse a Crossref 'page' value such as '101-120', 'pp. 101 - 12', 'e1034'."""
    s = re.sub(r"^\s*pp?\.\s*", "", _dash(s).strip(), flags=re.I)
    s = re.sub(r"\s+", "", s)
    m = re.fullmatch(r"(" + PAGE + r")(?:-(" + PAGE + r"))?", s)
    return page_range(m.group(1), m.group(2)) if m else None


def source_pages(source: str) -> list[tuple[str, int, int]]:
    """All page ranges (and, as a fallback, single pages) in a Source field."""
    text = _dash(source)
    ranges = [r for r in (page_range(a, b) for a, b in RANGE_RE.findall(text)) if r]
    singles = [r for r in (page_range(a) for a in SINGLE_RE.findall(text)) if r]
    return ranges or singles


def fmt_pages(r: tuple[str, int, int]) -> str:
    pre, a, b = r
    return f"{pre}{a}" if a == b else f"{pre}{a}-{pre}{b}"


def compare(ref: dict, entry: Path) -> list[str]:
    meta = vl.metadata(entry.read_text(encoding="utf-8"))
    diffs = []
    if meta.get("Year") and ref["year"] and str(ref["year"]) != meta["Year"].strip():
        diffs.append(f"year: entry {meta['Year']} vs Crossref {ref['year']}")
    if ref["pages"]:
        want = parse_pages(ref["pages"])
        src = meta.get("Source") or ""
        found = source_pages(src)
        if want is None:
            diffs.append(f"pages: Crossref value '{ref['pages']}' not parsable; "
                         f"entry source '{src}'")
        elif want not in found:
            seen = ", ".join(fmt_pages(r) for r in found) or "no page range"
            diffs.append(f"pages: Crossref {fmt_pages(want)} vs entry source "
                         f"'{src}' ({seen})")
    if meta.get("Title") and norm(meta["Title"]) != norm(ref["title"]):
        diffs.append(f"title differs:\n    entry:    {meta['Title']}\n    Crossref: {ref['title']}")
    if meta.get("Author(s)") and ref["authors"]:
        family = norm(ref["authors"][0].split(",")[0])
        if family and family not in norm(meta["Author(s)"]):
            diffs.append(f"first author: Crossref {ref['authors'][0]} not found in entry")
    return diffs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("doi")
    ap.add_argument("--entry", help="summary file to compare against")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    msg = fetch(args.doi)
    if msg is None:
        return 1
    ref = summarise(msg)
    if args.json:
        print(json.dumps(ref, indent=2, ensure_ascii=False))
    else:
        for k, v in ref.items():
            v = "; ".join(v) if isinstance(v, list) else v
            print(f"{k:<10} {v}")
    if args.entry:
        diffs = compare(ref, Path(args.entry))
        print("\nno discrepancy with the entry" if not diffs else "\nDISCREPANCIES "
              "(check against the front matter of the PDF; it decides):")
        for d in diffs:
            print(f"  - {d}")
        return 1 if diffs else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
