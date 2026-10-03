#!/usr/bin/env python3
"""Number guard: bind every number in a LaTeX manuscript to a frozen run or
to a sourced register of external numbers.

What it does
------------
Every numeric token in the manuscript (outside comments and the excluded
contexts listed below) must be found either

  (a) among the values of the CURRENT FROZEN RUN, with tolerance:
      decimal comma or point, rounding to the digits shown, factor 100
      (share vs. percent), thousands separators, sign; or
  (b) in the REGISTER OF EXTERNAL NUMBERS, exactly (no rounding, no scaling),
      so that a registered value cannot license a number of another magnitude.

Key results can be bound at label level, which removes the blind spot of
value-set matching (a stale number that happens to equal some other value of
the run):

  \\res{label}{value}   compared only against the run line with this label
  \\ext{key}{value}     compared only against this register row

Define both in the preamble so that they print their second argument:
  \\newcommand{\\res}[2]{#2}   \\newcommand{\\ext}[2]{#2}

The guard binds numbers to their origin. It does NOT establish that a
number is correct.

Inputs
------
  TEX ...            manuscript files (.tex); directories are scanned for *.tex
  --runs-dir DIR     folder with frozen runs and the pointer file
                     current_freeze.txt, which names the current run file
                     (written only after a complete, plausible run)
  --results FILE     explicit run file; overrides the pointer (a deviation
                     from pointer or newest run is reported)
  --register FILE    external numbers CSV: key,value,unit,source,page,retrieved
  --versions FILE    JSON: {"v1": {"required_modules": [...], "freeze": "<RUNID>"}}
  --version vN       draft version whose module list and pinned freeze apply
  --figures DIR --figures-src DIR
                     figures used by the manuscript vs. originals of the run:
                     md5-identical, originals not older than the run file

Run file formats (one run per file; run files are named *_<RUNID>.csv/.log)
-------------------------------------------------------------------------
  pipe log:  MODULE|BLOCK|label|value        value lines
             MODULE|STATUS|ok=<n>|failed=<n> one per module
             FREEZE <RUNID>                  written last by the master
  CSV:       header module,block,label,value; status rows use block STATUS
             with label ok=<n> and value failed=<n>; the freeze stamp is the
             row FREEZE,,run_id,<RUNID>

Excluded from the manuscript tokens
-----------------------------------
comments; the bibliography; arguments of reference, citation, label, input,
graphics, url and layout commands, including the whole cell content of
\\multicolumn and \\multirow; macro definitions (\\newcommand and similar);
tikzpicture environments; lengths with the unit attached
(12pt, 0.5\\textwidth); a length written with a space (12 pt) is treated as
a number; years 1900-2099; dates (2025-03-14, 14.03.2025) and
run IDs; digits inside identifiers (H1, v3, R^2). Integers up to
--ignore-int-upto N can be skipped on request (default -1: none are skipped).

Structural checks
-----------------
run file present and non-empty, with a run ID (fails first); FREEZE stamp;
no failed status and no ERROR lines; all modules required for --version
present; the pointer names the newest run; a freeze pinned for --version
equals the current one (a version-pinned checker must not go stale); run ID
verbatim in the manuscript (comments count); no open placeholders (TODO,
TBD, XXX, ??, \\todo) in the text; every register row has a value and a source;
figures (optional) as above.

Release rule: exit code 0 only if every number is bound and no structural
check fails; otherwise 1. Usage errors exit with 2.

Self-test
---------
  check_numbers.py --self-test
builds a synthetic run and manuscript in a temporary folder and confirms that
the guard passes the clean case and lengths with an attached unit, and fires
on: a single manipulated digit, a manipulated value inside \\res, a pointer
to an older run, a missing run, an incomplete run (module missing), an
unknown \\res label, a register value at another magnitude (\\ext), a
register value with a flipped sign and an unbound number followed by the
word 'in'.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import tempfile
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

POINTER = "current_freeze.txt"
RUNID_RE = re.compile(r"(\d{4}-\d{2}-\d{2}_\d{6})")
PLACEHOLDER_RE = re.compile(r"\bTODO\b|\bXXX\b|\?\?|\\todo\b|\bTBD\b")

# ---------------------------------------------------------------- numbers --

NUM_RE = re.compile(
    r"(?:(?<![A-Za-z0-9_^\\.,\-])[-\u2212\u2013])?"  # sign, not the 2nd dash of "--"
    r"(?<![A-Za-z0-9_^\\.,])"             # not part of an identifier / number
    r"\d+(?:[.,]\d+)*"                      # digits with separators
    r"(?![A-Za-z0-9_])"
)


def interpretations(token: str):
    """Yield (Decimal value, decimals shown) for each plausible reading."""
    s = token.replace("\u2212", "-").replace("\u2013", "-")
    sign = -1 if s.startswith("-") else 1
    s = s.lstrip("-")
    out = []

    def add(num: str, decimals: int):
        try:
            out.append((sign * Decimal(num), decimals))
        except InvalidOperation:
            pass

    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        thou = "." if dec == "," else ","
        intpart, frac = s.rsplit(dec, 1)
        add(intpart.replace(thou, "") + "." + frac, len(frac))
    elif "," in s or "." in s:
        sep = "," if "," in s else "."
        groups = s.split(sep)
        if len(groups) > 2:  # 1,234,567 or 1.234.567
            if all(len(g) == 3 for g in groups[1:]):
                add("".join(groups), 0)
        else:
            intpart, frac = groups
            add(intpart + "." + frac, len(frac))          # decimal reading
            if len(frac) == 3 and 1 <= len(intpart) <= 3:  # thousands reading
                add(intpart + frac, 0)
    else:
        add(s, 0)
    return out


def rounded(v: Decimal, decimals: int):
    q = Decimal(1).scaleb(-decimals)
    return {v.quantize(q, rounding=ROUND_HALF_UP), v.quantize(q, rounding=ROUND_HALF_EVEN)}


def match_tolerant(token: str, values: list) -> bool:
    for x, d in interpretations(token):
        ax = abs(x)
        for v in values:
            for cand in (v, v * 100, v / 100):
                try:
                    if ax in {abs(r) for r in rounded(cand, d)}:
                        return True
                except InvalidOperation:
                    continue
    return False


def match_exact(token: str, values: list) -> bool:
    for x, _ in interpretations(token):
        if any(x == v for v in values):
            return True
    return False


def numbers_in(text: str) -> list:
    vals = []
    for m in re.finditer(r"[-\u2212]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text):
        try:
            vals.append(Decimal(m.group(0).replace("\u2212", "-")))
        except InvalidOperation:
            pass
    return vals

# -------------------------------------------------------------- run files --


class Run:
    def __init__(self, path: Path):
        self.path = path
        self.records = []      # (module, block, label, value_text)
        self.run_id = None
        self.status_failed = []
        self.error_lines = []
        self._read()

    def _read(self):
        text = self.path.read_text(encoding="utf-8", errors="replace")
        if self.path.suffix.lower() == ".csv":
            rows = list(csv.DictReader(text.splitlines()))
            for r in rows:
                self._add(r.get("module", ""), r.get("block", ""),
                          r.get("label", ""), r.get("value", ""))
        else:
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("FREEZE "):
                    self.run_id = line.split(None, 1)[1].strip()
                elif re.match(r"^(ERROR|Error in)\b", line):
                    self.error_lines.append(line)
                elif line.count("|") == 3:
                    self._add(*[p.strip() for p in line.split("|")])

    def _add(self, module, block, label, value):
        if module == "FREEZE":
            self.run_id = value.strip()
        elif block == "STATUS":
            failed = re.search(r"failed=(\d+)", f"{label} {value}")
            if failed and int(failed.group(1)) > 0:
                self.status_failed.append(module)
        elif module.upper() == "ERROR" or value.startswith("ERROR"):
            self.error_lines.append(f"{module}|{block}|{label}|{value}")
        else:
            self.records.append((module, block, label, value))

    @property
    def modules(self):
        return {r[0] for r in self.records}

    def values(self):
        return [v for r in self.records for v in numbers_in(r[3])]

    def label_values(self, label):
        hits = [r for r in self.records if r[2] == label or "|".join(r[:3]) == label]
        return [v for r in hits for v in numbers_in(r[3])], bool(hits)


def run_files(runs_dir: Path):
    files = [p for p in runs_dir.iterdir()
             if p.suffix.lower() in (".csv", ".log") and RUNID_RE.search(p.name)]
    return sorted(files, key=lambda p: RUNID_RE.search(p.name).group(1))

# ------------------------------------------------------------- manuscript --

SKIP_CMDS = (
    r"ref|eqref|pageref|cref|Cref|autoref|nameref|label|cite[a-zA-Z]*|"
    r"input|include|includegraphics|url|href|bibliography|bibliographystyle|"
    r"addbibresource|usepackage|RequirePackage|documentclass|setlength|"
    r"addtolength|setcounter|addtocounter|vspace\*?|hspace\*?|linespread|"
    r"scalebox|resizebox|rule|multicolumn|multirow|cmidrule|cline|"
    r"addlinespace|arraystretch|renewcommand|newcommand|definecolor|"
    r"begin|end|hypersetup|geometry|captionsetup|graphicspath"
)
LENGTH_RE = re.compile(
    r"-?\d*\.?\d+(?:pt|cm|mm|in|em|ex|bp|sp|pc)\b"
    r"|-?\d*\.?\d+[ \t]*\\(?:text|line|column|paper)(?:width|height)\b")
DATE_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:(?:\\?_|T)\d{4,6})?|\b\d{1,2}\.\d{1,2}\.\d{4}\b|"
    r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\b")
YEAR_RE = re.compile(r"(?<!\d)(?<!\d[.,])(?:19|20)\d{2}(?!\d|[.,]\d)")


def blank(m) -> str:
    return re.sub(r"[^\n]", " ", m.group(0))


def strip_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", l) for l in text.split("\n"))


def skip_command_args(text: str) -> str:
    """Blank \\cmd[opt]{arg}{arg}... for layout/reference commands."""
    pat = re.compile(r"\\(?:" + SKIP_CMDS + r")\b\*?")
    out, pos = [], 0
    for m in pat.finditer(text):
        if m.start() < pos:
            continue
        out.append(text[pos:m.start()])
        i = m.end()
        while True:  # consume optional (...) [...] and {...} groups
            while i < len(text) and text[i] in " \t":
                i += 1
            if i < len(text) and text[i] in "[({":
                close = {"[": "]", "(": ")", "{": "}"}[text[i]]
                depth, j = 0, i
                while j < len(text):
                    if text[j] == text[i]:
                        depth += 1
                    elif text[j] == close:
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                i = j + 1
            else:
                break
        out.append(re.sub(r"[^\n]", " ", text[m.start():i]))
        pos = i
    out.append(text[pos:])
    return "".join(out)


def prepare(text: str):
    """Return (bound tokens, free tokens) with line numbers and sections."""
    text = strip_comments(text)
    text = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", blank, text, flags=re.S)
    text = re.sub(r"\\(?:printbibliography|bibliography)\b.*", blank, text, flags=re.S)
    text = re.sub(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", blank, text, flags=re.S)
    text = text.replace("{,}", ",")
    text = re.sub(r"(?<=\d)\\[,;: ](?=\d{3})", "", text)  # 12\,345 -> 12345

    bound = []
    for m in re.finditer(r"\\(res|ext)\{([^{}]*)\}\{([^{}]*)\}", text):
        line = text.count("\n", 0, m.start()) + 1
        bound.append((m.group(1), m.group(2), m.group(3).strip(), line))
    text = re.sub(r"\\(?:res|ext)\{[^{}]*\}\{[^{}]*\}", blank, text)

    text = skip_command_args(text)
    text = LENGTH_RE.sub(blank, text)
    text = DATE_RE.sub(blank, text)
    text = YEAR_RE.sub(blank, text)

    free, section = [], "(preamble)"
    for n, line in enumerate(text.split("\n"), 1):
        sec = re.search(r"\\(?:sub)*section\*?\{([^}]*)\}", line)
        if sec:
            section = sec.group(1)
        for m in NUM_RE.finditer(line):
            free.append((m.group(0), n, section))
    return bound, free, text

# ------------------------------------------------------------------ guard --


def load_register(path: Path, problems: list):
    reg = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for i, row in enumerate(csv.DictReader(fh), 2):
            key = (row.get("key") or "").strip()
            if not (row.get("value") or "").strip() or not (row.get("source") or "").strip():
                problems.append(f"register line {i} ({key or '?'}): value and source required")
                continue
            reg[key] = numbers_in(row["value"])
    return reg


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def guard(tex_files, runs_dir=None, results=None, register=None, versions=None,
          version=None, figures=None, figures_src=None, ignore_int_upto=-1,
          quiet=False) -> int:
    problems, unbound = [], []
    say = (lambda *a: None) if quiet else print

    # 1. locate the run
    newest = pointer_run = None
    if runs_dir:
        runs_dir = Path(runs_dir)
        files = run_files(runs_dir) if runs_dir.is_dir() else []
        newest = files[-1] if files else None
        ptr = runs_dir / POINTER
        if ptr.exists():
            name = ptr.read_text(encoding="utf-8").strip()
            pointer_run = runs_dir / name if name else None
    run_path = Path(results) if results else pointer_run
    if results and pointer_run and Path(results).resolve() != pointer_run.resolve():
        say(f"NOTE explicit run {results} deviates from pointer {pointer_run.name}")
    if run_path is None or not run_path.exists() or run_path.stat().st_size == 0:
        say(f"FAIL no run file (pointer/explicit path: {run_path})")
        return 1
    run = Run(run_path)
    if not run.run_id:
        say(f"FAIL run file {run_path.name} has no FREEZE stamp / run ID")
        return 1
    if newest and newest.resolve() != run_path.resolve():
        problems.append(f"run {run_path.name} is not the newest run ({newest.name})")

    # 2. structural checks on the run
    for m in run.status_failed:
        problems.append(f"module {m} reports failed steps")
    for line in run.error_lines:
        problems.append(f"error line in run: {line}")
    if version:
        spec = json.loads(Path(versions).read_text(encoding="utf-8")).get(version) if versions else None
        if spec is None:
            problems.append(f"version {version} not defined in {versions}")
        else:
            for mod in spec.get("required_modules", []):
                if mod not in run.modules:
                    problems.append(f"version {version}: required module {mod} missing from run")
            pinned = spec.get("freeze")
            if pinned and pinned != run.run_id:
                problems.append(f"version {version} pins freeze {pinned}, current is {run.run_id} "
                                "(update checker and freeze together)")

    reg = load_register(Path(register), problems) if register else {}
    reg_values = [v for vs in reg.values() for v in vs]
    run_values = run.values()

    # 3. manuscript
    paths = []
    for t in tex_files:
        t = Path(t)
        paths += sorted(t.rglob("*.tex")) if t.is_dir() else [t]
    runid_seen = False
    for path in paths:
        raw = path.read_text(encoding="utf-8", errors="replace")
        if run.run_id in raw.replace("\\_", "_"):
            runid_seen = True
        bound, free, clean = prepare(raw)
        for n, line in enumerate(clean.split("\n"), 1):
            if PLACEHOLDER_RE.search(line):
                problems.append(f"{path.name}:{n}: open placeholder")
        for kind, label, value, n in bound:
            if kind == "res":
                vals, found = run.label_values(label)
                if not found:
                    unbound.append(f"{path.name}:{n}: \\res{{{label}}}: label not in run")
                elif not match_tolerant(value, vals):
                    unbound.append(f"{path.name}:{n}: \\res{{{label}}}{{{value}}} "
                                   f"does not match run value(s) {[str(v) for v in vals]}")
            else:
                if label not in reg:
                    unbound.append(f"{path.name}:{n}: \\ext{{{label}}}: key not in register")
                elif not match_exact(value, reg[label]):
                    unbound.append(f"{path.name}:{n}: \\ext{{{label}}}{{{value}}} "
                                   f"differs from register {[str(v) for v in reg[label]]}")
        for token, n, sec in free:
            vals = interpretations(token)
            if vals and all(v == v.to_integral_value() and abs(v) <= ignore_int_upto
                            and d == 0 for v, d in vals):
                continue
            if match_tolerant(token, run_values) or match_exact(token, reg_values):
                continue
            unbound.append(f"{path.name}:{n}: {token}  [section: {sec}]")
    if paths and not runid_seen:
        problems.append(f"run ID {run.run_id} does not appear in the manuscript")

    # 4. figures
    if figures and figures_src:
        run_mtime = run_path.stat().st_mtime
        for src in sorted(Path(figures_src).iterdir()):
            dst = Path(figures) / src.name
            if not src.is_file():
                continue
            if not dst.exists():
                problems.append(f"figure {src.name} missing in {figures}")
            elif md5(src) != md5(dst):
                problems.append(f"figure {src.name} differs from the run's original")
            if src.stat().st_mtime < run_mtime - 1:
                problems.append(f"figure original {src.name} is older than the run")

    # 5. report
    say(f"run: {run_path.name}  (run ID {run.run_id}; {len(run.records)} value lines)")
    for u in unbound:
        say(f"UNBOUND {u}")
    for p in problems:
        say(f"FAIL    {p}")
    ok = not unbound and not problems
    say("RELEASE: all numbers bound, structure ok" if ok
        else f"BLOCKED: {len(unbound)} unbound number(s), {len(problems)} structural problem(s)")
    return 0 if ok else 1

# -------------------------------------------------------------- self-test --


def self_test() -> int:
    tex = (r"\newcommand{\res}[2]{#2}\newcommand{\ext}[2]{#2}" "\n"
           r"% FREEZE: 2025-02-01_120000" "\n"
           r"\section{Results}" "\n"
           r"The sample has 1,250 persons; the effect is \res{coef_x}{0.43} "
           r"and the share is 37.5\%. The benchmark is \ext{bench}{12.0}\%." "\n")
    good = ("module,block,label,value\nA,SAMPLE,n,1250\nB,MODEL,coef_x,0.4312\n"
            "B,DESC,share,0.3751\nA,STATUS,ok=2,failed=0\nB,STATUS,ok=2,failed=0\n"
            "FREEZE,,run_id,2025-02-01_120000\n")
    old = good.replace("0.4312", "0.3950").replace("2025-02-01_120000", "2025-01-20_090000")
    reg = "key,value,unit,source,page,retrieved\nbench,12.0,percent,Synthetic source,3,2025-01-01\n"
    versions = json.dumps({"v1": {"required_modules": ["A", "B"], "freeze": "2025-02-01_120000"}})

    cases = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        def setup(tex_text=tex, runs=(("2025-01-20_090000", old), ("2025-02-01_120000", good)),
                  pointer="frozen_results_2025-02-01_120000.csv"):
            d = root / f"case{len(cases)}"
            (d / "runs").mkdir(parents=True)
            for rid, body in runs:
                (d / "runs" / f"frozen_results_{rid}.csv").write_text(body)
            if pointer is not None:
                (d / "runs" / POINTER).write_text(pointer)
            (d / "paper.tex").write_text(tex_text)
            (d / "register.csv").write_text(reg)
            (d / "versions.json").write_text(versions)
            return d

        def run_case(name, expect, **kw):
            d = setup(**kw)
            code = guard([d / "paper.tex"], runs_dir=d / "runs", register=d / "register.csv",
                         versions=d / "versions.json", version="v1", quiet=True)
            cases.append((name, expect, code))

        run_case("clean manuscript passes", 0)
        run_case("manipulated digit fires", 1, tex_text=tex.replace("1,250", "1,260"))
        run_case("manipulated bound value fires", 1, tex_text=tex.replace("{0.43}", "{0.44}"))
        run_case("pointer to older run fires", 1,
                 pointer="frozen_results_2025-01-20_090000.csv")
        run_case("missing run fires", 1, runs=(), pointer="")
        run_case("incomplete run (module B missing) fires", 1,
                 runs=(("2025-02-01_120000",
                        "\n".join(l for l in good.splitlines() if not l.startswith("B,")) + "\n"),))
        run_case("unknown label fires", 1, tex_text=tex.replace("coef_x", "coef_y"))
        run_case("register value at another magnitude fires", 1,
                 tex_text=tex.replace(r"\ext{bench}{12.0}", r"\ext{bench}{1.2}"))
        run_case("register value with flipped sign fires", 1,
                 tex_text=tex.replace(r"\ext{bench}{12.0}", r"\ext{bench}{-12.0}"))
        run_case("unbound number before the word 'in' fires", 1,
                 tex_text=tex + "A value of 77.7 in the text.\n")
        run_case("lengths with attached unit pass", 0,
                 tex_text=tex + r"\\[6pt] \hskip 0.5\textwidth \kern-1.5ex" + "\n")

    failed = 0
    for name, expect, code in cases:
        ok = code == expect
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name} (exit {code}, expected {expect})")
    print("self-test passed" if not failed else f"self-test FAILED ({failed})")
    return 0 if not failed else 1

# ------------------------------------------------------------------- main --


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tex", nargs="*", help="manuscript .tex files or folders")
    ap.add_argument("--runs-dir")
    ap.add_argument("--results")
    ap.add_argument("--register")
    ap.add_argument("--versions")
    ap.add_argument("--version")
    ap.add_argument("--figures")
    ap.add_argument("--figures-src")
    ap.add_argument("--ignore-int-upto", type=int, default=-1)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.tex:
        ap.print_usage()
        return 2
    if not (args.runs_dir or args.results):
        print("error: give --runs-dir (with current_freeze.txt) or --results")
        return 2
    if args.version and not args.versions:
        print("error: --version needs --versions FILE")
        return 2
    return guard(args.tex, args.runs_dir, args.results, args.register, args.versions,
                 args.version, args.figures, args.figures_src, args.ignore_int_upto)


if __name__ == "__main__":
    sys.exit(main())
