# Example

Everything in this folder is **synthetic**. The papers "Doe 2024", "Roe 2023"
and "Moe 2025", their authors, journals, findings, page numbers and DOIs are
invented (DOIs use the reserved example prefix `10.5555`). The numbers in the
manuscript and in the frozen runs are invented as well.

- `vault/` — three summaries, two hubs, one synthesis, a taxonomy, a
  reference file and an operations journal. The synthesis is deliberately not
  yet listed in its hub, so that `add_to_hubs.py --audit` has something to
  find. `full_texts/` holds no PDFs, because full texts are never published.
- `manuscript/` — `paper.tex` with label-bound (`\res`, `\ext`) and free
  numbers; `runs/` with an older and a current frozen run and the pointer
  `current_freeze.txt`; `external_numbers.csv`; `guard_versions.json` with a
  current (`v2`) and a stale (`v1`) version pin.

See the quick start in the top-level README.
