# Staged procedure inference

Config-driven CLI for three-stage procedure extraction from clinical notes
(label → validate → revise). Entry point: `main.py`.

**In scope:** only these two staged `cvar`s:

| cvar | Bilateral | Notes |
|------|-----------|-------|
| `prior_procedures_staged` | yes (OD/OS) | Prior glaucoma procedures |
| `future_procedures_staged` | yes (OD/OS) | Proposed / future procedures |

## Quick start

```bash
cp .env.example .env   # fill in API keys and endpoints
python main.py --model_name qwen --cvar prior_procedures_staged --tok_num 500 --reasoning_effort none
```

Artifacts land under:

```text
results/{cvar}/{deployment_model_name}/{reasoning_effort}/{tok_num}_{mm-dd_HH:MM}/
```

Override the root with `RESULTS_ROOT` or `--results_root`. Each run writes:

- `prompt_snapshot.txt` — prompts used for the cvar
- `params_log.json` — model call parameters (once per run)
- `response_log.txt` — verbose per-note logs
- `server_failures.txt` — note indices that hit retriable server errors
- `stats.txt` — running exact-match accuracy on raw labels / drought metrics
- `max_count_tracker.txt` — token/max-count tracker
- `grading_results_{cvar}.csv` — checkpoint rewritten after every note
- `llm_results_{cvar}.csv` — final frame with `{model}_label_OD/OS` and AI columns

## Package layout

```text
config.py                 # env + model registry + RunContext
main.py                   # argparse → resolve → run
models/                   # provider adapters (shared BaseAdapter interface)
  base.py
  gpt_client.py           # Azure OpenAI Responses API
  anthropic_client.py     # Claude via AnthropicFoundry
  openai_compatible.py    # Grok / DeepSeek / Qwen chat completions
  registry.py             # create_adapter / create_client
prompts/registry.py       # cvar → PromptConfig (two entries)
extraction/extractor.py   # JSON parse helpers + column/key maps
tasks/staged.py           # generalized staged-procedures routine
tasks/runner.py           # grading-set loop
output/results_writer.py  # result artifacts
configs/prompt_config.py  # prompt template source of truth
```

## How a note is processed

For each note in the workbook:

1. **Task 1 (label)** — extract per-eye procedure labels + reasoning as JSON
2. **Task 2 (validate)** — check labels (`Yes`/`No` per eye); reasons recorded per eye
3. **Task 3 (revise)** — only if validation failed; otherwise skipped

Every stage returns `OD`, `OS`, `OD_reasoning`, `OS_reasoning`. `tasks/staged.py` formats reasoning from the `PromptConfig` field
maps. `extraction/extractor.py` parses the final JSON (direct parse → last
`{...}` block → field regex → failed sentinel).

## How to add a model

1. Add a `ModelSpec` in `config.py` (`MODEL_REGISTRY`) with alias, provider type,
   adapter name, deployment string, allowed `reasoning_effort` values, and env
   var names for key/endpoint.
2. If the provider needs new SDK quirks, add an adapter under `models/` that
   implements `generate(...)` and register it in `models/registry.py`
   `_ADAPTER_CLASSES`. Do **not** add `if model == ...` branches in the runner.

## How to add a staged prompt

1. Add the staged prompt dict (`task1_label` / `task2_validate` / `task3_revise`)
   to `configs/prompt_config.py`.
2. Add one `PromptConfig` entry in `prompts/registry.py` (`cvar`,
   `target_columns`, `prompts`). All stages share `PROCEDURES_SCHEMA`; override
   `schema` or the other defaulted fields only if the output shape differs.
3. Add matching entries in `extraction/extractor.py` (`CONFIG_TO_COLUMN`,
   `CVAR_OUTPUT_KEYS`) if the output keys / columns are new.

No changes to `tasks/staged.py` or `main.py` dispatch logic should be required.

## CLI flags

| Flag | Default | Meaning |
|------|---------|---------|
| `--model_name` | required | Registry alias (`gpt`, `claude`, `deepseek`, `grok_n`, `qwen`) |
| `--cvar` | required | One of the two staged cvars |
| `--tok_num` | 500 | Max tokens for the provider path |
| `--reasoning_effort` | `none` | Validated against the model's allowed set |
| `--data_xlsx` | from env / `data/` | Adjudicated notes workbook |
| `--results_root` | `results/` | Output root |

## Downstream steps

After inference, standardize then evaluate (see [README.md](README.md)):

```bash
python standardization/run.py --input <llm_results_{cvar}.csv> --output <llm_results_{acronym}_procedures_standardized.csv> \
  --prior-od-col "Prior glaucoma surgeries or lasers OD" {model}_label_OD \
  --prior-os-col "Prior glaucoma surgeries or lasers OS" {model}_label_OS
python evaluate.py --input <llm_results_{acronym}_procedures_standardized.csv>
```

## Dependencies

Runtime needs packages from `pyproject.toml` (`openai`, `anthropic`, `pandas`,
`openpyxl`, `tqdm`, …). Prompt templates live in `configs/prompt_config.py`.
