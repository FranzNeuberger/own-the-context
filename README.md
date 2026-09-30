# Own the Context, Rent the Model — starter kit

A topic-free template for building a **local, auditable research assistant**:
an agent-maintained, page-anchored literature memory in plain text, plus the
analysis and manuscript chain that binds every reported number to its origin.

This repository accompanies the article

> *Own the Context, Rent the Model: Design Principles for a Local, Auditable
> Research Assistant for Literature Synthesis and Statistical Analysis.*

Paper: working paper (SSRN, DOI
[10.2139/ssrn.7171998](https://doi.org/10.2139/ssrn.7171998)); journal
version under review.

Author: Franz Neuberger, German Youth Institute (DJI), Munich.
ORCID: [0000-0003-3427-0298](https://orcid.org/0000-0003-3427-0298)

Version: 1.0.0. The archive DOI (Zenodo) is minted with the first GitHub
release and added here afterwards (see "Releasing" below).

The repository contains the procedure, not a corpus. It ships no literature,
no data and no licensed text. The example is entirely made up. Every author,
paper, finding, page number, number and DOI in the example vault and the
example manuscript is invented and refers to no real study.

---

## Who this is for

Researchers who work with a command-line coding agent and want the agent's
reading of the literature, its analysis code and its manuscript numbers to be
**inspectable, repairable and portable**. The kit assumes you are comfortable
with Markdown, Git, Python and, for the analysis side, R and LaTeX. It does
not assume any particular field, model or vendor. Everything the kit asks you
to keep is held in open formats that open-source tools can read and write
(Markdown, YAML, CSV, R, LaTeX, Git, Python). Only the model and the agent
tool that calls it are rented.

---

## Core principles

Each principle is tied to an artefact in this repository that you can open
and check.

| # | Principle | What it means in practice | Artefact here |
|---|-----------|---------------------------|---------------|
| 1 | **Plain text first, locally held** | Markdown, YAML, CSV, R and LaTeX under version control; binary formats only at the edges and only where unavoidable (PDF in, PDF out; word-processor files for co-authors who do not work in LaTeX). `grep`, `diff` and the Git history are the repair tools. | the whole tree |
| 2 | **Every claim carries an address** | Each hard claim in a summary ends with a page anchor `(p. X)`. Metadata come from the front matter of the PDF. Corrections are recorded, never silent. | `templates/entry_template.md` |
| 3 | **Say only what the source says** | Wording rule: no paraphrase exceeds the scope, population or strength of the passage it cites. Claim-check notes record what a source does *not* support. Quotations are verbatim, checked against the rendered page. | `Quotable` section; claim-check bullets |
| 4 | **Declare the version** | Each summary names the version it summarises (working paper, preprint, online-first, print); anchors follow that pagination. Print beats working paper. Never convert pages by an offset. | `Version summarised` field; `contracts/fixer_brief.md` |
| 5 | **A second instance checks, without write rights** | A fresh-context verifier reads summary and PDF and reports; it does not edit. The fixer re-checks each finding before correcting. | `contracts/verifier_brief.md`, `contracts/fixer_brief.md` |
| 6 | **Curate the register, grow additively** | A controlled taxonomy with admissions, consolidations, reasoned rejections and pending proposals; curated hub notes that are only ever appended to, never rebuilt from tag lines. | `taxonomy.example.yaml`, `scripts/add_to_hubs.py`, `contracts/post_import_sync.md` |
| 7 | **Narrow mandates, written contracts, human gates** | Subagents write only their own entry; shared files are finalised by one main agent; new tags wait for the researcher's approval. Document content is data, never instruction. | `contracts/import_brief.md` |
| 8 | **Grounded maieutics** | A scheduled questioning pass over entry pairs across clusters; a new edge is written back only after the wording of both sources has been checked, and only with the researcher's approval. | `contracts/maieutic_pass_brief.md`, `templates/synthesis_template.md` |
| 9 | **The agent reads the map, not the microdata** | A machine-readable variable map (with waves, wording changes and filters) lets the agent write analysis code for data it never sees. The researcher runs the code; the agent reads aggregate output. | `templates/variable_map_template.csv`, `templates/availability_matrix_template.csv`, `templates/lookup_template.csv`, `templates/project_skeleton.md` |
| 10 | **One run, one protocol, one freeze** | Numbered scripts called in fixed order by one master script; one log per run; a dated freeze with a run ID; a pointer file names the current freeze. | `templates/project_skeleton.md` |
| 11 | **Every number bound** | A number guard checks the numbers in the LaTeX source, apart from the excluded contexts listed in the script, against the frozen run (with rounding tolerance) or against a sourced register of external numbers (exactly). Key results are bound at label level. It binds numbers to their origin; it does not prove them correct. | `scripts/check_numbers.py`, `templates/external_numbers_template.csv` |
| 12 | **Own the context, rent the model** | Memory, rules, maps, code and results are plain text in open formats, held by the researcher. The model is accessed through a provider's interface and can be replaced, although the agent briefs may need adapting to another tool. | the whole tree |

---

## Repository layout

```
README.md                  this file
LICENSE                    MIT (code), CC BY 4.0 (everything else) -- see "Licence"
CITATION.cff               how to cite
.zenodo.json               archive metadata for Zenodo
requirements.txt           Python dependency (PyYAML)
taxonomy.example.yaml      taxonomy structure with neutral example tags

templates/
  entry_template.md            summary template (metadata table, anchored sections)
  synthesis_template.md        synthesis note template
  variable_map_template.csv    variable map schema with 3 synthetic rows
  availability_matrix_template.csv  coverage per variable and wave, with
                               instrument-change columns (1 synthetic row)
  lookup_template.csv          raw name -> labels in two languages
                               (1 synthetic row)
  external_numbers_template.csv register of external numbers (header only)
  project_skeleton.md          layout and rules of the analysis project

contracts/                 agent briefs (fill in the placeholders)
  import_brief.md              one source, one agent, fresh context
  verifier_brief.md            read-only second instance
  fixer_brief.md               applies verified corrections, visibly
  maieutic_pass_brief.md       scheduled questioning pass
  post_import_sync.md          main-agent routine after each batch

scripts/                   Python 3.9+, standard library except yaml_lint.py
  vaultlib.py                  shared helpers (vault location, parsing)
  link_check.py                unresolved wikilinks (vault-wide name resolution)
  add_to_hubs.py               additive hub sync; hub-counter audit
  vault_stats.py               inventory; anchors, quotations (3-5), versions, RIS
  graph_stats.py               link-graph measures: mean degree, isolates,
                               cross-cluster share; optional CSV log
  yaml_lint.py                 taxonomy consistency; entry tags vs. taxonomy
  crossref_check.py            DOI lookup; compare with an entry's metadata
  check_numbers.py             number guard with self-test

example/
  vault/                       synthetic vault: 3 entries, 2 hubs, 1 synthesis
  manuscript/                  mini manuscript, two frozen runs, pointer,
                               register, version file
```

Vault layout expected by the scripts (change the constants at the top of
`scripts/vaultlib.py` if yours differs):

```
<vault>/
  stash/            inbox for new PDFs (not versioned)
  summaries/        one Markdown summary per source
  syntheses/        synthesis notes
  full_texts/       PDFs under the summary's stem (never public)
  hubs/<CATEGORY>/  one curated hub note per tag
  taxonomy.yaml
```

---

## Quick start

Requirements: Python 3.9 or newer, and `pip install -r requirements.txt` for
`yaml_lint.py`. Work on a copy so that the example stays intact.
`my_vault/` is git-ignored. Keep a real vault outside the clone.

```bash
cp -r example/vault my_vault
export VAULT_DIR="$PWD/my_vault"     # or pass --vault my_vault to each script

python3 scripts/link_check.py                 # all links resolve?
python3 scripts/add_to_hubs.py --audit        # reports 1 problem: the synthesis
                                              #   names a hub that does not list it yet
python3 scripts/add_to_hubs.py Synthesis_Remote_Work_Travel --dry-run
python3 scripts/add_to_hubs.py Synthesis_Remote_Work_Travel
python3 scripts/add_to_hubs.py --audit        # now clean
python3 scripts/vault_stats.py --all          # anchors, quotations (3-5), versions, RIS
python3 scripts/graph_stats.py                # full graph: 4 entries, 4 edges, 0 isolates;
                                              #   summaries only: 3 entries, 1 edge, 1 isolate
python3 scripts/graph_stats.py --summaries-only --list-isolates
                                              #   isolate: Moe_2025_Hybrid_Schedules_...
python3 scripts/graph_stats.py --log my_vault/graph_log.csv
                                              #   appends one dated row per graph
python3 scripts/yaml_lint.py --entries        # taxonomy + entry tags
                                              #   (warnings on selectivity are expected
                                              #   in a three-entry vault)

# Number guard
python3 scripts/check_numbers.py --self-test
python3 scripts/check_numbers.py example/manuscript/paper.tex \
    --runs-dir example/manuscript/runs \
    --register example/manuscript/external_numbers.csv \
    --versions example/manuscript/guard_versions.json --version v2
#   -> RELEASE (exit 0). Try --version v1: its pinned freeze is stale -> BLOCKED.
#   Change one digit in paper.tex (e.g. 28.7 -> 28.9) -> BLOCKED.
```

`vault_stats.py` flags a summary whose `Quotable` section holds fewer than
three or more than five quotations (one block quote per quotation). Change
the range with `--quotes-min`/`--quotes-max`, or require an exact count with
`--quotes N`.

`graph_stats.py` treats a wikilink between two entries as an undirected
edge. Links to hub notes are counted separately. An edge counts as
cross-cluster only if both entries link at least one CONCEPT hub and share
none. An edge with an entry that links no concept hub does not count as
cross-cluster. `--list-isolates` lists the
isolates of the first graph reported (the full graph, or the summaries-only
graph with `--summaries-only`). These are the candidates for the maieutic
pass (`contracts/maieutic_pass_brief.md`).

`crossref_check.py` needs network access and a real DOI. The example DOIs use
the reserved example prefix `10.5555` and will not resolve. It compares page
ranges after normalisation (dash variants, `p.`/`pp.`, spaces, abbreviated
last pages such as `101-12` for `101-112`).

### Starting your own vault

1. Create the folders above, outside the cloned repository, and copy
   `taxonomy.example.yaml` to `<vault>/taxonomy.yaml`, and replace the example
   tags with your own.
2. Put the import rules where your agent reads them on every session (for
   example, the agent's project instruction file), pointing to
   `contracts/import_brief.md` and `templates/entry_template.md`.
3. Import a first handful of sources one by one, then run the verification
   pass (`contracts/post_import_sync.md`, Phase 5) and a verifier on each.
4. Only then parallelise: one subagent per source under the import brief,
   shared files finalised by the main agent.

---

## Limits

- **Bring your own model.** The kit contains instructions and scripts, not a
  model. Any capable command-line agent can follow the briefs, but results depend
  on the model. The model and the agent tool are usually proprietary and paid
  for. Everything else the kit uses is open source and free of charge.
- **Inference sends text to the provider.** Whatever the agent reads — source
  text, summaries, code, aggregate output — passes through the model
  provider's interface. Keep confidential microdata outside the agent's
  reach (principle 9) and check your institution's rules before processing
  licensed or sensitive material.
- **Licensed PDFs never go into a public repository**, and neither do the
  summaries derived from them if their licence does not allow it.
  `.gitignore` excludes `*.pdf` and the quick-start copy `my_vault/`.
  Text-and-data-mining permissions, where they
  apply, cover analysis, not publication.
- **Checks are not proofs.** Anchors, verifiers and the number guard make
  errors findable, but they do not certify their absence. A verifier of the same
  model family may share the author's blind spots. The number guard binds a
  number to a frozen run or a register. It does not show that the number is
  right.
- **Not an evaluation.** The kit reproduces the procedure described in the
  article, not its figures. Your corpus, taxonomy and numbers will differ.

---

## Licence

- Code (`scripts/`): MIT License.
- Everything else (this README, `contracts/`, `templates/`, `example/`,
  `taxonomy.example.yaml` and the other documentation files): Creative
  Commons Attribution 4.0 International,
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

`LICENSE` holds the MIT text and the CC BY 4.0 notice with links to the
licence, and states the split by component. It is the authoritative
statement. The metadata files carry a single licence field:

- `CITATION.cff` sets `license: MIT`. CFF accepts a list of SPDX identifiers,
  but reads several identifiers as alternatives ("OR"), not as a split by
  component, so a list would misstate the terms.
- `.zenodo.json` sets `"license": "MIT"`. The Zenodo deposit metadata take
  one licence per record. The record's description and notes state that
  texts, templates, briefs and the example are CC BY 4.0.

## Citation

See `CITATION.cff`. Please cite the paper when you use or adapt the kit. Until
the journal version is published, `CITATION.cff` points to the SSRN working
paper.

---

## Releasing

The first public version is 1.0.0. The archive DOI comes from Zenodo, which
archives each GitHub release of the repository. The order of the steps
matters.

1. Create an empty public repository named `own-the-context` on GitHub.
   Do not let GitHub add a README, a licence or a `.gitignore`, so that the
   local history can be pushed without a merge.
2. Sign in to Zenodo with the GitHub account and switch the repository on
   under the GitHub integration. This has to happen before the first
   release, because Zenodo only archives releases made after the switch.
3. Connect the local clone and push it:
   `git remote add origin <repository URL>` and then
   `git push -u origin main`.
4. On GitHub, create the release `v1.0.0` from `main`. Zenodo reads
   `.zenodo.json`, archives the release and mints two DOIs. The version DOI
   names this release, and the concept DOI always resolves to the latest
   version.
5. Enter the concept DOI in the README (a DOI badge and the version line
   above) and in `CITATION.cff` (`doi` and `date-released`, see the comment
   at the top of that file). Commit and push. The metadata update needs no
   second release.

The commit author address becomes visible in a public repository. To keep a
personal address out of it, set the GitHub no-reply address as the
repository's `user.email` before the first push and rewrite the author of
the existing commit with `git commit --amend --reset-author`.

When the journal version is published, switch `preferred-citation` in
`CITATION.cff` to the article and add the article DOI to `.zenodo.json` as a
further related identifier.
