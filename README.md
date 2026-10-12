# LLM Procedure Extraction

Authored by Janet Kang and Nicholas Solages, McKnight Vision Research Center - Bascom Palmer Eye Institute

This repository is a framework for running large language models for extraction of glaucoma procedure
information from free-text glaucoma clinical notes. The pipeline addresses two tasks — prior glaucoma
procedures (surgeries, lasers, and implants performed before the encounter) and future procedures
(interventions proposed or recommended at the encounter). The pipeline standardizes labels and model
outputs and subsequently evaluates model performance.

The inference framework (model adapters, staged label → validate → revise runner, results writers) is
adapted from [llmnotes / GLLaucoMed](https://github.com/swarupswaminathan/llmnotes), which applies the
same workflow to glaucoma medications. The prompts, standardization, and evaluation here are specific
to procedures. See [Citation](#citation).

---

## Pipeline overview

```text
1. Inference     python main.py ...
                 → results/{cvar}/{model}/{effort}/{tok_num}_{ts}/llm_results_{cvar}.csv

2. Standardize   python standardization/run.py --input <csv> --output <standardized.csv> ...
                 → llm_results_{acronym}_procedures_standardized.csv

3. Evaluate      python evaluate.py --input <standardized.csv>
                 → {acronym}_results.txt
```

Supported staged `cvar`s:

| cvar | Acronym | Bilateral | Ground-truth columns | Description |
|------|---------|-----------|----------------------|-------------|
| `prior_procedures_staged` | prior | yes (OD/OS) | `Prior glaucoma surgeries or lasers OD` / `OS` | Prior glaucoma procedures |
| `future_procedures_staged` | future | yes (OD/OS) | `Other proposed intervention OD` / `OS` | Proposed / future procedures |

---

## Project structure

```text
llm_procedures/
├── main.py                 # Inference CLI
├── evaluate.py             # Evaluation CLI
├── config.py               # Env loading, model registry, RunContext
├── configs/
│   └── prompt_config.py    # Prompt template source of truth
├── models/                 # Provider adapters (GPT, Claude, OpenAI-compatible, Qwen)
├── prompts/
│   └── registry.py         # cvar → PromptConfig (schemas, keys, columns)
├── extraction/
│   └── extractor.py        # Parse model JSON; cvar → target columns
├── tasks/
│   ├── staged.py           # Label → validate → revise for one note
│   └── runner.py           # Grading-set loop
├── output/
│   └── results_writer.py   # Csv, stats, failure logs
├── evaluation/             # Metrics vs adjudicated labels
├── standardization/        # Procedure label standardizer + CLI
├── data/                   # Input xlsx (adjudicated notes; not tracked)
├── results/                # Inference outputs (default RESULTS_ROOT; not tracked)
├── Dockerfile
├── pyproject.toml / uv.lock
├── .env.example
├── README.md
└── INFERENCE.md            # Inference package details (models, prompts)
```

See [INFERENCE.md](INFERENCE.md) for model/prompt extension guides, and
[standardization/README.md](standardization/README.md) for the
standardizer rules and API.

---

## Setup

Requires **Python 3.11+**.

```bash
# Clone and enter the repo
cd llm_procedures   # or your checkout path

# Install with uv (recommended)
uv sync

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Copy and fill secrets:

```bash
cp .env.example .env
# Set AZURE_API_KEY, QWEN_API_KEY, endpoints, etc.
```

Optional path overrides (also in `.env`):

- `DATA_XLSX`, `RESULTS_ROOT`

Place the adjudicated notes workbook under `data/` (or point `DATA_XLSX` at your path). It needs one
row per note with `PAT_ENC_CSN_ID`, `NOTE_ID`, `ENC_CONTACT_DATE`, `Combined_NOTE_TEXT`, and the
ground-truth columns for the cvar being run. `data/`, `results/`, and all `.xlsx` / `.csv` files are
git-ignored — clinical notes must never be committed.

---

## Inference

```bash
python main.py \
  --model_name qwen \
  --cvar prior_procedures_staged \
  --tok_num 500 \
  --reasoning_effort none
```

Registered model aliases (see `config.py`): `gpt`, `claude`, `deepseek`,
`grok_n`, `qwen`.

Outputs land under:

```text
results/{cvar}/{deployment_model}/{reasoning_effort}/{tok_num}_{mm-dd_HH:MM}/
```

Artifacts include `llm_results_{cvar}.csv`, `prompt_snapshot.txt`,
`params_log.json`, `response_log.txt`, `stats.txt`, and failure trackers. The results file holds the
input rows plus `{model}_label_OD`, `{model}_label_OS`, `AI_Diagnosis`, `AI_Explanation`, and
`AI_Reasoning`.

Full details: [INFERENCE.md](INFERENCE.md).

---

## Standardization

The same deterministic standardizer is applied to the adjudicated labels and the model labels so the
two can be compared directly. Pass every column to standardize, by eye:

```bash
python standardization/run.py \
  --input results/prior_procedures_staged/.../llm_results_prior_procedures_staged.csv \
  --output results/prior_procedures_staged/.../llm_results_prior_procedures_standardized.csv \
  --prior-od-col "Prior glaucoma surgeries or lasers OD" qwen_label_OD \
  --prior-os-col "Prior glaucoma surgeries or lasers OS" qwen_label_OS
```

Name the output `llm_results_{acronym}_procedures_standardized.csv`. For `future_procedures_staged`, use `--future-od-col "Other proposed intervention OD" qwen_label_OD`
and `--future-os-col "Other proposed intervention OS" qwen_label_OS`. Each processed column `X` gains
`X_standardized` and `X_parsed_items`. See
[standardization/README.md](standardization/README.md).

---

## Evaluation

```bash
python evaluate.py \
  --input path/to/llm_results_prior_procedures_standardized.csv
```

`--cvar` / `--acronym` are optional when the filename is a known standardized basename, and
`--model_name` is optional when the file holds one model's labels. Writes `{acronym}_results.txt`
beside the input
(override with `--output`). Evaluation is eye-level (two samples per note) and reports exact match,
presence/absence accuracy, sensitivity, specificity, precision, recall, F1, multiset Jaccard, Gwet
AC1, a date-weighted hierarchical Jaccard, Jaccard by procedure count, and MAE / MSE of procedure
counts. Pass `--seed` for reproducible bootstrap confidence intervals and `--verbose` to list every
mismatched eye.

---

## Docker

```bash
docker build -t llm-procedure-extraction .
docker run --env-file .env llm-procedure-extraction python main.py --help
```

Secrets are injected at runtime via `--env-file` or `-e`; they are not baked
into the image.

---

## Dependencies

Declared in `pyproject.toml` / `uv.lock`. Core runtime packages include
`openai`, `anthropic`, `pandas`, `openpyxl`, `numpy`, `tqdm`, `rapidfuzz`,
`scipy`, `scikit-learn`, `statsmodels`.

---

## Citation

The inference framework in this repository is adapted from:

> Solages N. *GLLaucoMed (llmnotes)*: a framework for running large language models for extraction of
> medication information from free-text glaucoma clinical notes. McKnight Vision Research Center,
> Bascom Palmer Eye Institute. <https://github.com/swarupswaminathan/llmnotes>
