#!/usr/bin/env python3
"""Inventory and format checks for the vault.

Reports, per vault:
  - counts of summaries, syntheses, full texts and hubs
  - stem pairing: summaries without a full text, full texts without a summary
  - tag use per category (from the Graph rows)
and, per summary (flagged only when something is off):
  - empty 'Version summarised' field               (principle: declare the version)
  - page anchors '(p. X)' in the summary           (principle: every claim has an address)
  - bullets under 'Key findings' without an anchor
  - number of quotations under 'Quotable' outside the range
    --quotes-min..--quotes-max (default 3-5; one quotation = one block of
    consecutive '>' lines)
  - RIS block missing or TY/ER records unbalanced
  - quarantine notice present (legacy entries awaiting rewrite)

Usage:
  vault_stats.py [--vault DIR] [--quotes-min 3] [--quotes-max 5]
                 [--quotes N] [--json] [--all]

--quotes N is shorthand for an exact count (--quotes-min N --quotes-max N)
and cannot be combined with --quotes-min or --quotes-max.

--all lists every summary, not only flagged ones. Exit code is always 0;
the script informs, it does not gate. Use the verification pass for gating.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vaultlib as vl  # noqa: E402

ANCHOR_RE = re.compile(r"\((?:p|pp)\.\s*[A-Za-z]?\d+(?:\s*[-–]\s*[A-Za-z]?\d+)?[^)]*\)")
RIS_RE = re.compile(r"```ris\s*\n(.*?)```", re.S)
QUARANTINE_RE = re.compile(r"QUARANTINE", re.I)


def count_quotations(quotable: str) -> int:
    """Count block quotes: each run of consecutive '>' lines is one."""
    count, inside = 0, False
    for line in quotable.splitlines():
        is_quote = line.lstrip().startswith(">")
        if is_quote and not inside:
            count += 1
        inside = is_quote
    return count


def check_summary(path: Path, qmin: int, qmax: int) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta = vl.metadata(text)
    findings = vl.section(text, "Key findings")
    bullets = []  # a bullet plus its indented continuation lines
    for line in findings.splitlines():
        if line.lstrip().startswith(("- ", "* ")):
            bullets.append(line)
        elif bullets and line.startswith((" ", "	")) and line.strip():
            bullets[-1] += " " + line.strip()
        elif not line.strip() and bullets:
            bullets.append("")  # blank line ends the bullet
    bullets = [b for b in bullets if b]
    unanchored = [l.strip() for l in bullets if not ANCHOR_RE.search(l)]
    quotable = vl.section(text, "Quotable")
    n_quotes = count_quotations(quotable)
    ris = RIS_RE.search(text)
    ris_ok = False
    if ris:
        body = ris.group(1)
        ty = len(re.findall(r"^TY  - ", body, re.M))
        er = len(re.findall(r"^ER  -", body, re.M))
        ris_ok = ty == er and ty > 0

    issues = []
    if not meta.get("Version summarised"):
        issues.append("version field empty")
    if unanchored:
        issues.append(f"{len(unanchored)} key-finding bullet(s) without page anchor")
    if not qmin <= n_quotes <= qmax:
        expected = str(qmin) if qmin == qmax else f"{qmin}-{qmax}"
        issues.append(f"{n_quotes} quotation(s) under Quotable (expected {expected})")
    if not ris_ok:
        issues.append("RIS block missing or unbalanced")
    if QUARANTINE_RE.search(text):
        issues.append("quarantine notice present")
    return {
        "anchors": len(ANCHOR_RE.findall(text)),
        "quotes": n_quotes,
        "issues": issues,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    vl.add_vault_arg(ap)
    ap.add_argument("--quotes-min", type=int, default=None, metavar="N",
                    help="minimum number of quotations per summary (default 3)")
    ap.add_argument("--quotes-max", type=int, default=None, metavar="N",
                    help="maximum number of quotations per summary (default 5)")
    ap.add_argument("--quotes", type=int, default=None, metavar="N",
                    help="exact number of quotations; shorthand for "
                         "--quotes-min N --quotes-max N")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true", help="list every summary")
    args = ap.parse_args()
    if args.quotes is not None:
        if args.quotes_min is not None or args.quotes_max is not None:
            ap.error("--quotes cannot be combined with --quotes-min/--quotes-max")
        qmin = qmax = args.quotes
    else:
        qmin = 3 if args.quotes_min is None else args.quotes_min
        qmax = 5 if args.quotes_max is None else args.quotes_max
    if qmin < 0 or qmin > qmax:
        ap.error(f"invalid quotation range {qmin}-{qmax}")

    vault = vl.resolve_vault(args.vault)
    summaries = vl.entry_stems(vault, include_syntheses=False)
    syntheses = {k: v for k, v in vl.entry_stems(vault).items() if k not in summaries}
    ft_dir = vault / vl.FULL_TEXTS_DIR
    pdfs = {p.stem for p in ft_dir.glob("*.pdf")} if ft_dir.is_dir() else set()
    hubs = vl.hub_files(vault)

    tag_use = collections.Counter()
    per_entry = {}
    for stem, path in summaries.items():
        for ref in vl.graph_hub_refs(path.read_text(encoding="utf-8")):
            tag_use[ref.split("/")[0]] += 1
        per_entry[stem] = check_summary(path, qmin, qmax)

    report = {
        "summaries": len(summaries),
        "syntheses": len(syntheses),
        "full_texts": len(pdfs),
        "hubs": len(hubs),
        "summaries_without_full_text": sorted(set(summaries) - pdfs),
        "full_texts_without_summary": sorted(pdfs - set(summaries)),
        "tag_links_per_category": dict(sorted(tag_use.items())),
        "anchors_total": sum(e["anchors"] for e in per_entry.values()),
        "entries": per_entry,
    }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"summaries: {report['summaries']}   syntheses: {report['syntheses']}   "
          f"full texts: {report['full_texts']}   hubs: {report['hubs']}")
    print(f"page anchors in summaries: {report['anchors_total']}")
    print("tag links per category: " + ", ".join(
        f"{k}={v}" for k, v in report["tag_links_per_category"].items()))
    if report["summaries_without_full_text"]:
        print(f"summaries without full text: {len(report['summaries_without_full_text'])}"
              " (expected in a public copy; full texts stay private)")
    for stem in report["full_texts_without_summary"]:
        print(f"full text without summary: {stem}.pdf")
    flagged = 0
    for stem, e in per_entry.items():
        if e["issues"] or args.all:
            flagged += bool(e["issues"])
            state = "; ".join(e["issues"]) or "ok"
            print(f"  {stem}: anchors={e['anchors']} quotes={e['quotes']} -- {state}")
    print(f"summaries flagged: {flagged} of {len(per_entry)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
