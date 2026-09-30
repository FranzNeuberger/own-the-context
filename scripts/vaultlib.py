"""Shared helpers for the vault scripts (standard library only).

Every script locates the vault in this order:
  1. the --vault argument,
  2. the VAULT_DIR environment variable,
  3. the current working directory.

Default layout (relative to the vault root; change the constants below if your
vault uses other folder names):

  summaries/          one Markdown summary per source
  syntheses/          synthesis notes (not tied to a single PDF); entry names
                      must be unique across summaries/ and syntheses/
  full_texts/         PDFs under the same stem as their summary (never public)
  hubs/<CATEGORY>/    one curated hub note per tag
  taxonomy.yaml       the controlled vocabulary
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SUMMARIES_DIR = "summaries"
SYNTHESES_DIR = "syntheses"
FULL_TEXTS_DIR = "full_texts"
HUBS_DIR = "hubs"
TAXONOMY_FILE = "taxonomy.yaml"

# Folders never scanned for notes or link targets.
SKIP_DIRS = {".git", ".obsidian", ".trash", "__pycache__", "node_modules"}

# Hub notes: a counter line and a list section.
HUB_COUNTER_RE = re.compile(r"^Entries:[ \t]*(\d+)[ \t]*$", re.M)
HUB_LIST_HEADING = "## Linked entries"

WIKILINK_RE = re.compile(r"(!?)\[\[([^\[\]\n]+?)\]\]")
FENCE_RE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.M | re.S)
# A run of n backticks opens inline code that only a run of exactly n closes.
INLINE_CODE_RE = re.compile(r"(?<!`)(`+)(?!`)[^\n]+?(?<!`)\1(?!`)")
META_ROW_RE = re.compile(r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(.*?)\s*\|\s*$", re.M)


def add_vault_arg(parser) -> None:
    parser.add_argument(
        "--vault",
        help="vault root (default: $VAULT_DIR, else the current directory)",
    )


def resolve_vault(arg: str | None) -> Path:
    raw = arg or os.environ.get("VAULT_DIR") or "."
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        sys.exit(f"error: vault directory not found: {path}")
    return path


def iter_markdown(root: Path):
    """Yield all .md files below root, skipping hidden and tool folders."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
        ]
        for name in sorted(filenames):
            if name.endswith(".md"):
                yield Path(dirpath) / name


def iter_files(root: Path):
    """Yield all files below root (any extension), skipping hidden folders."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
        ]
        for name in filenames:
            if not name.startswith("."):
                yield Path(dirpath) / name


def strip_code(text: str) -> str:
    """Blank out fenced code blocks and inline code, keeping line numbers."""
    blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))  # noqa: E731
    text = FENCE_RE.sub(blank, text)
    return INLINE_CODE_RE.sub(blank, text)


def parse_wikilink(inner: str) -> str:
    """Return the link target of [[target#heading^block|alias]]."""
    # Obsidian escapes the alias pipe as "\|" inside Markdown tables.
    target = re.split(r"\\?\|", inner, 1)[0]
    target = target.split("#", 1)[0]
    target = target.split("^", 1)[0]
    return target.strip()


def wikilinks(text: str):
    """Yield (line_number, target, is_embed) for every wikilink outside code."""
    clean = strip_code(text)
    for m in WIKILINK_RE.finditer(clean):
        line = clean.count("\n", 0, m.start()) + 1
        target = parse_wikilink(m.group(2))
        if target:
            yield line, target, bool(m.group(1))


def metadata(text: str) -> dict[str, str]:
    """Parse the metadata table rows of the form | **Field** | value |.

    The first occurrence of a field wins: the metadata table comes first, and
    later tables in the same note (e.g. the Methods table, which also has a
    'Source' row) must not overwrite it.
    """
    meta: dict[str, str] = {}
    for k, v in META_ROW_RE.findall(text):
        meta.setdefault(k.strip(), v.strip())
    return meta


def section(text: str, heading: str) -> str:
    """Return the body of a '## heading' section (up to the next '## ')."""
    pattern = re.compile(
        r"^##\s+" + re.escape(heading) + r"\s*$(.*?)(?=^##\s|\Z)", re.M | re.S
    )
    m = pattern.search(text)
    return m.group(1) if m else ""


def hub_links(text: str) -> list[str]:
    """Return the targets listed in a hub note's list section, in order."""
    body = section(text, HUB_LIST_HEADING.lstrip("# ").strip())
    return [t for _, t, _ in wikilinks(body)]


def entry_stems(vault: Path, include_syntheses: bool = True) -> dict[str, Path]:
    """Map entry stem -> path for summaries (and optionally syntheses).

    Entry names must be unique across summaries/ and syntheses/ (compared
    case-insensitively, as links resolve). On a collision the first entry
    (the summary) is kept and a warning goes to stderr.
    """
    stems: dict[str, Path] = {}
    seen: dict[str, Path] = {}
    folders = [SUMMARIES_DIR] + ([SYNTHESES_DIR] if include_syntheses else [])
    for folder in folders:
        base = vault / folder
        if base.is_dir():
            for p in sorted(base.glob("*.md")):
                if p.name.lower() == "readme.md":
                    continue
                first = seen.setdefault(p.stem.lower(), p)
                if first is not p:
                    print(f"warning: entry name '{p.stem}' is not unique "
                          f"({first.relative_to(vault).as_posix()} and "
                          f"{p.relative_to(vault).as_posix()}); keeping the "
                          "first, links to it are ambiguous", file=sys.stderr)
                    continue
                stems[p.stem] = p
    return stems


def hub_files(vault: Path) -> dict[str, Path]:
    """Map 'CATEGORY/Tag' -> hub path."""
    hubs: dict[str, Path] = {}
    base = vault / HUBS_DIR
    if base.is_dir():
        for p in sorted(base.glob("*/*.md")):
            hubs[f"{p.parent.name}/{p.stem}"] = p
    return hubs


def graph_hub_refs(text: str) -> list[str]:
    """Return 'CATEGORY/Tag' for each [[hubs/CATEGORY/Tag]] in the Graph row."""
    row = metadata(text).get("Graph", "")
    refs = []
    for _, target, _ in wikilinks(row):
        parts = target.split("/")
        if len(parts) >= 3 and parts[-3] == HUBS_DIR:
            refs.append(f"{parts[-2]}/{parts[-1]}")
    return refs


if __name__ == "__main__":
    print(__doc__.strip())
    print("\nLibrary module imported by the other scripts. It has no command-line options.")
