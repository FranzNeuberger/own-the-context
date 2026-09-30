# Post-import sync (routine)

Run after every import or batch of parallel imports, by the MAIN agent only.
It brings the controlled vocabulary, the hub notes and the graph links back
into a consistent state. Subagents never run it.

```
Phase 0  Load context: taxonomy.yaml, project instructions.
Phase 1  Taxonomy check of all NEWTAG proposals -> decision table
         (admit / map to an existing tag / reject, each with a reason).
         >> STOP: present the table to the researcher and wait for approval <<
         Record decisions in taxonomy.yaml: admitted tags in `taxonomy`,
         mappings in `consolidations`, rejections in `rejected_tags`,
         undecided items in `proposed_additions`.
Phase 2  Tag cleaning of all entries against the taxonomy
         (apply consolidations, flag invalid tags: yaml_lint.py --entries).
         Bulk edits by script only, backup first, dry run before live run.
Phase 3  Hubs, additively only: add_to_hubs.py <Stem> for each new entry.
         Append; never rebuild a hub list from tag lines.
Phase 4  Set or renew the Graph row links in the new entries.
Phase 5  Verification pass and report:
         - link_check.py            (all links resolve)
         - add_to_hubs.py --audit   (counters equal list lengths)
         - vault_stats.py           (anchors, 3-5 quotations, versions, RIS)
         - RIS records balanced; new titles present in the canonical file
         - stash empty only after all of the above
         - after an agent crash: the disk state counts, not the report
         Report admitted / mapped / rejected tags, files touched, open items;
         one line in the operations journal.
```

**Idempotence:** safe to run repeatedly. Valid tags stay unchanged, existing
hubs are updated, never duplicated. Rerunning after an interruption converges
on the state of a single complete run.

**Invariant:** never regenerate curated structures from derived data. Hub
lists are curated; tag lines are a derived index. A hub rebuilt from tags
silently deletes curated links.

**Admission rule for new tags:** the tag must discriminate — used by more
than one entry and by fewer than half of the corpus.
