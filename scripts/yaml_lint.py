#!/usr/bin/env python3
"""Lint the taxonomy file and, optionally, the tags used in the entries.

Taxonomy checks (taxonomy.yaml):
  - top-level keys present: taxonomy, consolidations, rejected_tags,
    proposed_additions (statistics is optional)
  - every category holds a list of unique tags; no tag in two categories
  - every consolidation names a canonical tag that is admitted, and its
    merged_from variants are NOT admitted themselves
  - no rejected tag is admitted
  - every proposed addition has tag, category, date and a valid status

Entry checks (--entries):
  - every #Tag in a Tags row is admitted, or is flagged as unknown
  - tags that are consolidation variants are flagged with their canonical form
  - selectivity: tags used by exactly one entry, or by at least half of all
    entries, are reported (admission rule: more than one entry, fewer than
    half of the corpus)

Usage:
  yaml_lint.py [--vault DIR] [--taxonomy FILE] [--entries]

Requires PyYAML (pip install pyyaml).
Exit code: 0 if no errors (warnings allowed), 1 otherwise.
"""
from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vaultlib as vl  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("error: PyYAML is required (pip install pyyaml)")

REQUIRED_KEYS = ["taxonomy", "consolidations", "rejected_tags", "proposed_additions"]
VALID_STATUS = {"review_needed", "borderline", "admitted", "mapped", "rejected"}
TAG_RE = re.compile(r"#([A-Za-z0-9_\-]+)")


def lint_taxonomy(tax: dict, errors: list, warnings: list) -> set:
    for key in REQUIRED_KEYS:
        if key not in tax:
            errors.append(f"missing top-level key '{key}'")
    admitted: dict[str, str] = {}
    for category, tags in (tax.get("taxonomy") or {}).items():
        if not isinstance(tags, list):
            errors.append(f"category {category}: expected a list of tags")
            continue
        seen = set()
        for tag in tags:
            if tag in seen:
                errors.append(f"category {category}: duplicate tag {tag}")
            seen.add(tag)
            if tag in admitted and admitted[tag] != category:
                errors.append(f"tag {tag} in two categories: {admitted[tag]}, {category}")
            admitted[tag] = category

    for name, rule in (tax.get("consolidations") or {}).items():
        rule = rule or {}
        canonical = rule.get("canonical", name)
        if canonical not in admitted:
            errors.append(f"consolidation {name}: canonical tag {canonical} is not admitted")
        for variant in rule.get("merged_from") or []:
            if variant in admitted:
                errors.append(f"consolidation {name}: variant {variant} is still admitted")
        if not rule.get("reason"):
            warnings.append(f"consolidation {name}: no reason recorded")

    for session, items in (tax.get("rejected_tags") or {}).items():
        for item in items or []:
            tag = (item or {}).get("tag")
            if tag in admitted:
                errors.append(f"rejected tag {tag} ({session}) is admitted")
            if not (item or {}).get("reason"):
                warnings.append(f"rejected tag {tag} ({session}): no reason recorded")

    for i, item in enumerate(tax.get("proposed_additions") or [], 1):
        item = item or {}
        for field in ("tag", "category", "date", "status"):
            if not item.get(field):
                errors.append(f"proposed_additions #{i}: missing '{field}'")
        if item.get("status") and item["status"] not in VALID_STATUS:
            errors.append(f"proposed_additions #{i}: invalid status '{item['status']}'")
    return set(admitted)


def lint_entries(vault: Path, tax: dict, admitted: set, errors: list, warnings: list):
    variants = {}
    for name, rule in (tax.get("consolidations") or {}).items():
        rule = rule or {}
        for v in rule.get("merged_from") or []:
            variants[v] = rule.get("canonical", name)
    use = collections.Counter()
    entries = vl.entry_stems(vault)
    for stem, path in entries.items():
        row = vl.metadata(path.read_text(encoding="utf-8")).get("Tags", "")
        for tag in TAG_RE.findall(row):
            use[tag] += 1
            if tag in variants:
                errors.append(f"{stem}: tag #{tag} -> use #{variants[tag]}")
            elif tag not in admitted:
                errors.append(f"{stem}: tag #{tag} is not in the taxonomy "
                              "(propose it; do not add silently)")
    n = len(entries)
    for tag, k in sorted(use.items()):
        if k == 1:
            warnings.append(f"tag #{tag} used by one entry only (low selectivity)")
        elif n >= 4 and k >= n / 2:
            warnings.append(f"tag #{tag} used by {k} of {n} entries (too generic?)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    vl.add_vault_arg(ap)
    ap.add_argument("--taxonomy", help=f"taxonomy file (default: <vault>/{vl.TAXONOMY_FILE})")
    ap.add_argument("--entries", action="store_true", help="also check entry tags")
    args = ap.parse_args()

    vault = vl.resolve_vault(args.vault)
    path = Path(args.taxonomy) if args.taxonomy else vault / vl.TAXONOMY_FILE
    try:
        tax = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        print(f"error: cannot read {path}: {exc}")
        return 1

    errors, warnings = [], []
    admitted = lint_taxonomy(tax, errors, warnings)
    if args.entries:
        lint_entries(vault, tax, admitted, errors, warnings)
    for w in warnings:
        print(f"WARNING {w}")
    for e in errors:
        print(f"ERROR   {e}")
    print(f"admitted tags: {len(admitted)}; errors: {len(errors)}; warnings: {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
