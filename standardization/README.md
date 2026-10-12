# Procedure Label Standardization

This repository standardizes free-text **prior** and **future** glaucoma/cataract
**procedure** labels into a consistent format for downstream review and analysis.

It is the procedure-oriented counterpart to the `med_standardization` library. Where
`med_standardization` standardizes medication labels, this project standardizes
procedure labels using the rules described in
[`../configs/prompt_config.py`](../configs/prompt_config.py).

The standardizer is a deterministic, rule-based parser (no LLM calls). It takes an
already-extracted, per-eye procedure label and normalizes its formatting.

## What it does

This standardizer is applied to **both** the LLM task output labels and the human
grader "true" labels so that the two can be compared directly. Because the same
procedure can be written many ways, the standardizer maps every abbreviation/synonym
to a single canonical name and emits procedures in a single canonical order, so that
identical procedures always produce an identical string.

The input is a per-eye procedure label such as:

* `trab MMC OD 3/2018, phaco + goniotomy 6/12/2024`
* `phaco/IOL+AGI in anterior chamber (10/3/18)`
* `? SLT`

The standardizer applies the formatting rules from `configs/prompt_config.py` that
operate on an extracted label:

| Rule | Description | Example |
|------|-------------|---------|
| R4 | Date normalization (`prior` labels only) | `5/5/15` -> `5/5/2015`, `6/2015` kept |
| R5 | Expand shorthand, keep acronyms | `trab` -> `trabeculectomy`; `SLT` kept; `trab360`/`trabeculectomy 360` -> `Trab 360` (distinct procedure) |
| R6 | Preserve details in parentheses (canonical order); device model/size stay in the name | `SLT temp` -> `SLT (temporal)`; `Ahmed FP7 sulcus` -> `AGI FP7 (sulcus)` |
| R7 | Uncertainty | `? trab` / `may have had trab` -> `possible trabeculectomy`; `2000?` -> `~2000`; `1990s` -> `~1990s` |
| R8 | Allowed inference | `pseudophakia`/`PCO`/`IOL`/`PCIOL` -> `CEIOL`; `aphakia` -> `CE`; `tube` -> `tube shunt` |
| R9 | Combined same-day procedures joined by `/`, components ordered alphabetically | `goniotomy + phaco` -> `CEIOL/goniotomy`; `Phaco iStent` -> `CEIOL/iStent`; `phaco-Hydrus` -> `CEIOL/Hydrus` |
| R11 | `None` fallback | empty / `None` -> `None` |
| ORDER | Output ordered chronologically, then alphabetically | `CEIOL, BGI, Xen` -> `BGI, CEIOL, Xen` |
| SYN | Synonyms consolidate to one canonical name | `LI` -> `LPI`; `YAG` -> `YAG capsulotomy` |

Laterality (R3) and temporal scope (R1/R2) are assumed to be **already resolved** by
the choice of source column (prior vs. future, OD vs. OS). Any stray `OD`/`OS`/`OU`
tokens in the text are stripped, and the explicit `(laterality unknown)` placeholder is
preserved.

### Dashes

A dash separates a combination only when a known procedure name sits on **both** sides of
it, because a dash is otherwise punctuation inside a single procedure:

| Input | Output | Why |
|-------|--------|-----|
| `phaco-Hydrus` | `CEIOL/Hydrus` | two procedure names -> a combination |
| `phaco-KDB-goniotomy` | `CEIOL/KDB` | every dash in a chain separates |
| `KDB-goniotomy` | `KDB` | two names, but one procedure (`ABSORBED_BY_ADJACENT_CANONICAL`) |
| `i-stent`, `Ex-PRESS`, `5-FU` | `iStent`, `Express shunt`, `5FU injection` | hyphen inside one name |
| `phaco-IOL` | `CEIOL` | the lens suffix, dash or slash |
| `Ahmed FP7 - sulcus` | `AGI FP7 (sulcus)` | the dash introduces a detail |
| `BGI-350`, `Ahmed-FP7` | `BGI 350`, `AGI FP7` | device model / plate size |
| `trab 2018-2019` | `trabeculectomy 2018` | not a procedure name on either side |

Hyphens, non-breaking hyphens, en dashes, and em dashes are all recognized
(`HYPHEN_CHARS`), since labels are often pasted from notes.

### Future labels carry no date

A proposed procedure has not happened yet, so any date in a `future` label says when the
procedure is *planned* rather than when it occurred. The future rules format a proposed
procedure as `[procedure] ([detail])`, so the standardizer drops the date:
`TRABECULECTOMY 1/2018` -> `trabeculectomy`. The date is still parsed out of the text, so
no part of it is mistaken for a procedural detail (`Omni 360 2/10/23` -> `Omni (360)`).
Because nothing in a future list is dated, it is ordered alphabetically.

### Ordering

The output list is ordered to be stable and comparable:

1. **Chronologically** by date (ascending). A procedure dated only to a year or decade
   sorts at the start of that year.
2. Procedures **without a date** come after all dated procedures.
3. Ties (same date, or two undated procedures) are broken **alphabetically**.

Example: `LI 2010, CEIOL, YAG 3/24/2022` -> `LPI 2010, YAG capsulotomy 3/24/2022, CEIOL`.

## Repository structure

```text
standardization/
├── src/
│   ├── __init__.py
│   ├── constants.py                 # procedure vocabulary, detail maps, tokens. customize to your institution's conventions
│   ├── models.py                    # ParsedProcedure / ProcedureComponent dataclasses
│   ├── matching.py                  # bounded fuzzy matching for procedure names
│   ├── utils.py                     # date/detail/uncertainty/combine helpers
│   ├── parser.py                    # parse + order + render
│   └── procedure_standardization.py # main entry point
├── run.py                           # CSV batch runner
├── tests/
│   └── test_procedures.py
├── requirements.txt
└── README.md
```

## Installation

```bash
pip install -r requirements.txt
```

## Library usage

```python
from src.procedure_standardization import standardize_procedure_label

result = standardize_procedure_label(
    "trab MMC OD 3/2018, phaco + goniotomy 6/12/2024",
    label_type="prior",   # "prior" or "future"
)

print(result["standardized_procedure_list"])
# trabeculectomy MMC 3/2018, phaco/goniotomy 6/12/2024
```

Returned dictionary:

```python
{
  "input_type": "prior",
  "raw_input": "trab MMC OD 3/2018, phaco + goniotomy 6/12/2024",
  "standardized_procedure_list": "trabeculectomy MMC 3/2018, phaco/goniotomy 6/12/2024",
  "parsed_items": [ ... ],          # structured per-entry parse (logging/debug info)
  "failed_match": False,            # True if any procedure was ambiguous/unmapped
}
```

You can run the module directly to see worked examples:

```bash
python -m src.procedure_standardization
```

## Batch CSV processing (`run.py`)

`run.py` reads a CSV, standardizes one or more procedure columns, and writes a new CSV.

### Arguments

* `--input` — path to the input CSV (required)
* `--output` — path to the output CSV (required)
* `--prior-od-col` — column(s) with prior procedures for the right eye (OD)
* `--prior-os-col` — column(s) with prior procedures for the left eye (OS)
* `--future-od-col` — column(s) with future procedures for the right eye (OD)
* `--future-os-col` — column(s) with future procedures for the left eye (OS)

Each column argument accepts one or more column names, and any subset of the four may
be provided.

### Example

```bash
python run.py \
    --input procedures.csv \
    --output procedures_standardized.csv \
    --prior-od-col "Prior Procedures OD" \
    --prior-os-col "Prior Procedures OS" \
    --future-od-col "Future Procedures OD" \
    --future-os-col "Future Procedures OS"
```

### Output columns

For each processed input column, two columns are inserted immediately to its right:

* `<input_col> standardized` — the standardized procedure label
* `<input_col> parsed_items` — JSON with all logging/debugging information (analogous
  to the `parsed_items` column in `med_standardization`), including the per-entry
  parse, per-component confidence flags, correction notes, and the
  `failed_match` flag.

Cells that are empty or `None` become the string `"None"` (R11).

## Customization

All controlled vocabulary lives in `src/constants.py` and is intended to be tuned to
your institution's conventions:

* `PROCEDURE_SYNONYMS` — maps shorthand/brand/variant spellings to a single canonical
  output form. **Edit the right-hand side to change the canonical output.**
* `MODEL_TOKENS` — device model/size tokens (e.g. `FP7`, `250`, `350`) kept in the name.
* `DETAIL_*` — the detail vocabulary rendered inside parentheses.
* `EQUIVALENT_CANONICAL_GROUPS`, `ABSORBED_BY_ADJACENT_CANONICAL`,
  `NEVER_STARTS_PROCEDURE` — control where a space-separated combination is split, i.e.
  when two neighboring procedure names are really one procedure (`KDB goniotomy`,
  `Ahmed glaucoma drainage implant`, `SLT laser`) rather than a combination
  (`Phaco iStent`).
* `WHOLE_NAME_ONLY_VARIANTS` — instrument names, and names too vague to absorb trailing
  words, so they match only a complete procedure name (`laser`, `argon laser`).
* `EXCLUDED_CANONICALS` — procedures recognized only so they can be removed from the
  output (`AC paracentesis`).
* `POSSIBLE_TOKENS`, `STATUS_PREFIXES`, `NONE_TOKENS`, etc.

### Design notes / known ambiguities

Because the standardizer's job is to make two labels comparable, every procedure is
resolved to **one** canonical form defined in `PROCEDURE_SYNONYMS`. Notable choices:

* `Ahmed` / `AGI` -> `AGI` (alphanumeric model kept with a space: `AGI FP7`)
* `Baerveldt` / `BGI` / `BVT` -> `BGI` (plate size kept with a space, in any input
  order: `BGI350`, `BGI 350`, `350 BGI` -> `BGI 350`)
* `Clearpath` / `CP` -> `CP250` / `CP350`
* `phaco/IOL`, `cataract surgery`, `pseudophakia`, `PCO`, `IOL`, `PCIOL`, `MFIOL`,
  `ACIOL`, `phaco`, `phacoemulsification` -> `CEIOL`
* `LI` / `PI` / `laser iridotomy` / `peripheral iridotomy` / `laser peripheral iridotomy` -> `LPI`
* `laser iridoplasty` / `argon laser iridoplasty` / `ALPI` -> `iridoplasty`
* `trab revision` / `revision of trab` / `trabeculectomy (flap) revision` -> `bleb revision`
  (a revision remains a separate procedure from the original trabeculectomy)
* `YAG` / `YLC` / `capsulotomy` -> `YAG capsulotomy`
* `laser` / `laser surgery` / `laser procedure` -> `laser`, the generic procedure used
  when the type of laser is never specified. A named laser always wins, both on its own
  (`YAG laser` -> `YAG capsulotomy`) and beside the generic word (`SLT laser` -> `SLT`)
* `LTP` / `laser trabeculoplasty` -> `SLT`; `argon laser` -> `ALT`. A bare
  `trabeculoplasty` is left unmapped, since it could be either laser
* `MIGS` / `minimally invasive glaucoma surgery` -> `MIGS`. When combined with
  cataract extraction (`CE/MIGS`), `CE` is upgraded to `CEIOL` so the label matches
  `CEIOL/MIGS`. `GSL` / `goniosynechialysis` does the same (`CE/GSL` ->
  `CEIOL/goniosynechialysis`). The upgrade also applies when CE and CEIOL are
  named together
  (`cataract extraction with Phaco` -> `CEIOL`; `GATT 360 with cataract extraction
  with Phaco` -> `CEIOL/GATT (360)`)
* `AC paracentesis` / `paracentesis` is recognized and then **dropped** (R1 excludes
  it as a non-surgical event). A label that contains only an excluded procedure
  becomes `None`
* `possible` is written in lowercase and always placed first
* MMC / 5FU stay on the procedure name (`trabeculectomy MMC`, `bleb needling 5FU
  injection`). A documented dose (`10 mg 5FU`, `0.4 mg MMC`) is dropped.

Procedure names resolve on the **leading token(s)** first, so trailing descriptors are
absorbed (e.g. `KDB goniotomy` -> `KDB`). The exception is the handful of instrument /
very vague names in `WHOLE_NAME_ONLY_VARIANTS`, which are accepted only as a complete
name: `laser` alone is the generic laser procedure and `argon laser` alone is an ALT, but
`laser suture lysis` (excluded by R1) is left unmapped for review rather than relabeled. Fuzzy matching still
corrects typos
(`trabeculctomy` -> `trabeculectomy`). Anything that cannot be mapped is preserved
verbatim and flagged via `failed_match` so it can be reviewed and, if needed,
added to `PROCEDURE_SYNONYMS`.

If you prefer different canonical forms, change them in `PROCEDURE_SYNONYMS`.

### Suggested optional rules (not enabled by default)

* **Collapse date granularity for comparison.** If one grader writes `SLT 6/2015` and
  another `SLT 2015`, they will differ. An optional "compare at year granularity" mode
  could treat these as equal.

## Tests

```bash
python -m pytest tests/test_procedures.py
```

The suite covers normalization, date handling, detail preservation, uncertainty,
combined-procedure formatting, duplicate handling, the `None` fallback, and the
returned data shape.
