#!/usr/bin/env python3
"""Connectivity measures of the entry-to-entry link graph.

vault_stats.py counts entries; this script measures the relations between
them. Nodes are summaries and, by default, syntheses. An edge is a wikilink
between two entries, undirected and deduplicated. Links to hub notes are not
edges; they are counted separately.

Measures, reported for two graphs:
  full graph      summaries plus syntheses (the reference figure)
  summaries only  for comparison with measurements taken before syntheses
                  were included; syntheses are densely linked, and leaving
                  them out understates connectivity considerably

  1. mean degree        2 * edges / entries (hub links shown separately)
  2. isolates           entries without any entry-to-entry edge; these are
                        the candidates for the maieutic question pass
  3. cross-cluster share
                        edges whose two entries both link at least one
                        CONCEPT hub but share none, divided by all edges;
                        depends on hub coverage, so read it as a trend;
                        concept membership is read from [[hubs/CONCEPT/Tag]]
                        links; dangling hub links are reported by
                        link_check.py

Read every measure as a trend over dated runs, not as an evaluation.

Usage:
  graph_stats.py [--vault DIR] [--summaries-only] [--list-isolates]
                 [--log FILE.csv] [--json]

--log appends one row per reported graph to a CSV file (created with a
header if missing or empty), so that runs can be compared over time.
Exit code is always 0; the script informs, it does not gate.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vaultlib as vl  # noqa: E402

CONCEPT = "CONCEPT"
LOG_FIELDS = ["date", "graph", "entries", "edges", "mean_degree",
              "hub_links_per_entry", "isolates", "isolate_share",
              "cross_cluster_edges", "cross_cluster_share"]


def hub_ref(target: str) -> tuple[str, str] | None:
    """Return (CATEGORY upper-cased, tag lower-cased) if the link points to a
    hub note (case-insensitive, as link_check.py resolves), else None."""
    parts = target.strip().split("/")
    if len(parts) >= 3 and parts[-3].lower() == vl.HUBS_DIR.lower():
        return parts[-2].upper(), parts[-1].removesuffix(".md").lower()
    return None


def build_graph(entries: dict[str, Path]):
    """Return (edges, hub link counts, concept hubs per entry)."""
    by_lower = {stem.lower(): stem for stem in entries}
    edges = set()
    hub_links = collections.Counter()
    concepts = collections.defaultdict(set)
    for stem, path in sorted(entries.items()):
        text = path.read_text(encoding="utf-8", errors="replace")
        for _, target, _ in vl.wikilinks(text):
            ref = hub_ref(target)
            if ref:
                hub_links[stem] += 1
                if ref[0] == CONCEPT.upper():
                    concepts[stem].add(ref[1])
                continue
            base = target.split("/")[-1].removesuffix(".md").removesuffix(".pdf")
            other = by_lower.get(base.lower())
            if other and other != stem:
                edges.add(tuple(sorted((stem, other))))
    return edges, hub_links, concepts


def measure(label: str, entries: dict[str, Path]) -> dict:
    edges, hub_links, concepts = build_graph(entries)
    n, m = len(entries), len(edges)
    degree = collections.Counter()
    for a, b in edges:
        degree[a] += 1
        degree[b] += 1
    isolates = sorted(set(entries) - set(degree))
    cross = sum(1 for a, b in edges
                if concepts[a] and concepts[b] and not concepts[a] & concepts[b])
    return {
        "graph": label,
        "entries": n,
        "edges": m,
        "mean_degree": round(2 * m / n, 2) if n else 0.0,
        "hub_links_per_entry": round(sum(hub_links.values()) / n, 1) if n else 0.0,
        "isolates": len(isolates),
        "isolate_share": round(len(isolates) / n, 3) if n else 0.0,
        "cross_cluster_edges": cross,
        "cross_cluster_share": round(cross / m, 3) if m else 0.0,
        "isolate_list": isolates,
    }


def report(r: dict) -> None:
    print(f"\n-- {r['graph']}")
    print(f"entries: {r['entries']}; entry-to-entry edges "
          f"(undirected, deduplicated): {r['edges']}")
    print(f"1. mean degree: {r['mean_degree']:.2f} "
          f"(hub links, separate: {r['hub_links_per_entry']:.1f} per entry)")
    print(f"2. isolates: {r['isolates']} ({r['isolate_share'] * 100:.0f} %)")
    print(f"3. cross-cluster edges (no shared {CONCEPT} hub): "
          f"{r['cross_cluster_edges']}/{r['edges']} "
          f"({r['cross_cluster_share'] * 100:.0f} %)")


def append_log(path: Path, results: list[dict]) -> None:
    new = not path.exists() or path.stat().st_size == 0
    today = datetime.date.today().isoformat()
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LOG_FIELDS)
        if new:
            w.writeheader()
        for r in results:
            w.writerow({"date": today, **{k: r[k] for k in LOG_FIELDS[1:]}})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    vl.add_vault_arg(ap)
    ap.add_argument("--summaries-only", action="store_true",
                    help="report the summaries-only graph alone")
    ap.add_argument("--list-isolates", "-v", action="store_true",
                    help="list the isolates of the first reported graph")
    ap.add_argument("--log", metavar="FILE",
                    help="append the measures to a CSV file")
    ap.add_argument("--json", action="store_true", help="print JSON instead")
    args = ap.parse_args()

    vault = vl.resolve_vault(args.vault)
    summaries = vl.entry_stems(vault, include_syntheses=False)
    results = []
    if not args.summaries_only:
        results.append(measure("full graph (summaries + syntheses)",
                               vl.entry_stems(vault, include_syntheses=True)))
    results.append(measure("summaries only", summaries))

    if args.log:
        append_log(Path(args.log), results)
    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    for r in results:
        report(r)
    if args.list_isolates:
        print("\nisolates (candidates for the question pass):")
        for stem in results[0]["isolate_list"]:
            print("  ", stem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
