#!/usr/bin/env python3
"""Report wikilinks that do not resolve to a file in the vault.

Resolution follows the rules of common Markdown vault editors, which resolve
a bare note name against the whole vault, not only the current folder:

  [[Note]]                 any file whose stem is 'Note' (case-insensitive)
  [[folder/Note]]          any file whose path ends with 'folder/Note'
  [[Note#Heading|alias]]   heading, block reference and alias are ignored
  [[image.png]]            non-Markdown targets must match with extension

A naive check that looks only next to the linking file produces false
positives; this script does not. Code blocks and inline code are ignored.

Usage:
  link_check.py [--vault DIR] [--exclude PATTERN ...] [--quiet]

Exit code: 0 if every link resolves, 1 otherwise.
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vaultlib as vl  # noqa: E402


def build_index(vault: Path):
    """Return (set of lowercase stems, list of lowercase relative paths)."""
    stems, paths = set(), []
    for p in vl.iter_files(vault):
        rel = p.relative_to(vault).as_posix().lower()
        paths.append(rel)
        if rel.endswith(".md"):
            stems.add(p.stem.lower())
            paths.append(rel[:-3])  # allow links without '.md'
        else:
            stems.add(p.name.lower())
    return stems, paths


def resolves(target: str, stems: set, paths: list) -> bool:
    t = target.strip().lower().lstrip("./")
    if t.endswith(".md"):
        t = t[:-3]
    if "/" not in t:
        return t in stems
    return any(p == t or p.endswith("/" + t) for p in paths)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    vl.add_vault_arg(ap)
    ap.add_argument("--exclude", action="append", default=[],
                    help="glob (relative path) of notes not to scan, repeatable")
    ap.add_argument("--quiet", action="store_true", help="print the summary only")
    args = ap.parse_args()

    vault = vl.resolve_vault(args.vault)
    stems, paths = build_index(vault)

    broken, n_links, n_notes = [], 0, 0
    for note in vl.iter_markdown(vault):
        rel = note.relative_to(vault).as_posix()
        if any(fnmatch.fnmatch(rel, pat) for pat in args.exclude):
            continue
        n_notes += 1
        text = note.read_text(encoding="utf-8", errors="replace")
        for line, target, _ in vl.wikilinks(text):
            n_links += 1
            if not resolves(target, stems, paths):
                broken.append((rel, line, target))

    if not args.quiet:
        for rel, line, target in broken:
            print(f"{rel}:{line}: unresolved [[{target}]]")
    print(f"notes scanned: {n_notes}; links: {n_links}; unresolved: {len(broken)}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
