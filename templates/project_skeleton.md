# Analysis project skeleton

A generic layout for the analysis side (all names are placeholders). Version control
of the project code is recommended. Microdata never enter the project.

```
project/                      # version control recommended
|-- 00_main.R                 # single entry point; calls modules in fixed
|                             #   order, writes one log per run, ends with
|                             #   FREEZE <RUNID>
|-- config.R                  # labels, palette, two-language lookup, theme
|-- 01_load_prepared.R        # loads the prepared long-format file
|-- 02_descriptives.R
|-- 03_models.R
|-- 03a_addon_<name>.R        # added module, hooked in after 03
|-- 04_tables_figures.R
|-- 05_text_numbers.R         # computes the numbers the text reports,
|                             #   including differences and ratios
|-- checks/
|   |-- 90_plausibility.R
|   |-- 91_reliability.R      # on the analysis sample
|   `-- 92_text_vs_table.R
|-- map/
|   |-- variable_map.csv      # see templates/variable_map_template.csv
|   |-- availability_matrix.csv  # see templates/availability_matrix_template.csv
|   |-- lookup.csv            # see templates/lookup_template.csv
|   `-- codebook.md           # wording, filters, weights, change log
|-- output/                   # tables and figures of the frozen run
|-- logs/
|   |-- run_<RUNID>.log       # value lines, status lines, freeze stamp
|   |-- current_freeze.txt    # names the current frozen run; updated only
|   |                         #   after the plausibility block has passed
|   `-- testrun_<date>.log    # marked as not part of the master
|-- external_numbers.csv      # see templates/external_numbers_template.csv
|-- REPRODUCTION.md           # start a run, outputs, guard, failures
|-- drafts/
|   `-- paper_vN.tex
|-- check_numbers.py          # number guard (scripts/check_numbers.py)
|-- word_count.py
`-- quarantine/               # superseded scripts, moved, not deleted

# Outside the tree, not synchronised to a cloud service, not readable by the
# agent: <protected_store>/ holding the microdata and the prepared file.
```

## Rules

- Modules carry two-digit numbers and run in that order. An added module takes
  a letter suffix and follows the module it depends on. Checks use a separate
  numeric range (90+). Only the master is started directly.
- Value lines have the form `MODULE|BLOCK|label|value`. Each module closes with
  `MODULE|STATUS|ok=<n>|failed=<n>`, and the master closes a successful run
  with `FREEZE <RUNID>`. Labels are stable across runs (label-level binding).
- The agent writes code from the variable map and the codebook, and the
  researcher runs it. The agent reads aggregate output and logs only. If
  something looks wrong, the agent writes a data test (tabulation, range
  check), and the researcher runs it.
- Fallbacks fail loudly or are logged. A label must name the model actually
  estimated.
- The comment header of each script names the methods entry it implements
  (as a wikilink). The methods entry lists the scripts that implement it.
