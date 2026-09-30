#!/usr/bin/env python3
"""Append an entry to its hub notes additively, or audit all hubs.

Invariant: curated structures are never regenerated from derived data. A hub
list holds links the researcher set or accepted; the tag lines of the entries
are a derived index of those decisions, not their source. This script
therefore only ever APPENDS a link and sets the counter to the actual list
length. It never removes, reorders or rebuilds a list.

Hub note format (hubs/<CATEGORY>/<Tag>.md):

    # <Tag>

    Category: <CATEGORY>
    Entries: <n>

    ## Linked entries

    - [[Entry_Stem_One]]
    - [[Entry_Stem_Two]]

Usage:
  add_to_hubs.py STEM [--hub CATEGORY/Tag ...] [--create-missing] [--dry-run]
      Append [[STEM]] to the hubs named in the entry's Graph row
      (or to the hubs given with --hub).
  add_to_hubs.py --audit [--fix-counters]
      Check every hub: counter equals list length, no duplicate links,
      every listed entry exists, and every entry whose Graph row names the
      hub is listed. --fix-counters only corrects counters.

Exit code: 0 on success / clean audit, 1 on problems.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vaultlib as vl  # noqa: E402

HUB_SKELETON = """# {tag}

Category: {category}
Entries: 0

## Linked entries

"""


def set_counter(text: str, n: int) -> str:
    if vl.HUB_COUNTER_RE.search(text):
        return vl.HUB_COUNTER_RE.sub(f"Entries: {n}", text, count=1)
    # No counter yet: insert one after the title line.
    lines = text.splitlines(keepends=True)
    lines.insert(1 if lines else 0, f"\nEntries: {n}\n")
    return "".join(lines)


def append_link(text: str, stem: str) -> str:
    """Insert '- [[stem]]' after the last list item of the list section."""
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines)
                     if l.strip() == vl.HUB_LIST_HEADING)
    except StopIteration:
        lines += ["", vl.HUB_LIST_HEADING, ""]
        start = len(lines) - 2
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    last_item = max((i for i in range(start + 1, end)
                     if lines[i].lstrip().startswith("- ")), default=start + 1)
    lines.insert(last_item + 1, f"- [[{stem}]]")
    return "\n".join(lines).rstrip("\n") + "\n"


def add(vault: Path, stem: str, hubs: list[str], create: bool, dry: bool) -> int:
    entries = vl.entry_stems(vault)
    if stem not in entries:
        print(f"error: no entry '{stem}' in {vl.SUMMARIES_DIR}/ or {vl.SYNTHESES_DIR}/")
        return 1
    if not hubs:
        hubs = vl.graph_hub_refs(entries[stem].read_text(encoding="utf-8"))
    if not hubs:
        print(f"error: '{stem}' has no [[{vl.HUBS_DIR}/CATEGORY/Tag]] links in its Graph row")
        return 1

    status = 0
    for ref in hubs:
        category, tag = ref.split("/", 1)
        path = vault / vl.HUBS_DIR / category / f"{tag}.md"
        if path.exists():
            text = path.read_text(encoding="utf-8")
        elif create:
            text = HUB_SKELETON.format(tag=tag, category=category)
        else:
            print(f"MISSING HUB {ref} (use --create-missing after the tag is admitted)")
            status = 1
            continue
        links = vl.hub_links(text)
        if stem in links:
            new = set_counter(text, len(links))
            action = "already listed"
        else:
            new = append_link(text, stem)
            new = set_counter(new, len(vl.hub_links(new)))
            action = "appended"
        n = len(vl.hub_links(new))
        print(f"{ref}: {action}; counter -> {n}" + (" [dry run]" if dry else ""))
        if not dry and new != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new, encoding="utf-8")
    return status


def audit(vault: Path, fix: bool) -> int:
    entries = vl.entry_stems(vault)
    hubs = vl.hub_files(vault)
    declared: dict[str, set] = {ref: set() for ref in hubs}
    for stem, path in entries.items():
        for ref in vl.graph_hub_refs(path.read_text(encoding="utf-8")):
            declared.setdefault(ref, set()).add(stem)

    problems = 0
    for ref, path in hubs.items():
        text = path.read_text(encoding="utf-8")
        links = vl.hub_links(text)
        m = vl.HUB_COUNTER_RE.search(text)
        counter = int(m.group(1)) if m else None
        if counter != len(links):
            problems += 1
            print(f"{ref}: counter {counter} != list length {len(links)}"
                  + (" -> fixed" if fix else ""))
            if fix:
                path.write_text(set_counter(text, len(links)), encoding="utf-8")
        dups = sorted({l for l in links if links.count(l) > 1})
        for d in dups:
            problems += 1
            print(f"{ref}: duplicate link [[{d}]] (remove by hand)")
        for l in links:
            if l not in entries:
                problems += 1
                print(f"{ref}: listed entry [[{l}]] not found")
        for stem in sorted(declared.get(ref, set()) - set(links)):
            problems += 1
            print(f"{ref}: [[{stem}]] names this hub in its Graph row but is not "
                  f"listed (run: add_to_hubs.py {stem})")
    for ref in sorted(set(declared) - set(hubs)):
        problems += 1
        print(f"{ref}: named in Graph rows of {sorted(declared[ref])} but no hub note exists")
    print(f"hubs audited: {len(hubs)}; problems: {problems}")
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    vl.add_vault_arg(ap)
    ap.add_argument("stem", nargs="?", help="entry file stem (without .md)")
    ap.add_argument("--hub", action="append", default=[],
                    help="CATEGORY/Tag; overrides the Graph row, repeatable")
    ap.add_argument("--create-missing", action="store_true",
                    help="create hub notes that do not exist yet")
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    ap.add_argument("--audit", action="store_true", help="audit all hubs")
    ap.add_argument("--fix-counters", action="store_true",
                    help="with --audit: set counters to the actual list length")
    args = ap.parse_args()

    vault = vl.resolve_vault(args.vault)
    if args.audit:
        return audit(vault, args.fix_counters)
    if not args.stem:
        ap.error("give an entry STEM or --audit")
    return add(vault, args.stem, args.hub, args.create_missing, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
