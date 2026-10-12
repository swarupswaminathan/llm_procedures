"""Task/prompt registry for the two staged procedure cvars."""

from __future__ import annotations

from dataclasses import dataclass, field

import configs.prompt_config as prompt_config


@dataclass(frozen=True)
class StageSchema:
    properties: dict[str, dict[str, str]]
    required: list[str]


def _str_prop() -> dict[str, str]:
    return {"type": "string"}


# One schema for every stage: per-eye label + per-eye citation/explanation.
# Stage 2 reuses the keys with "Yes"/"No" labels and the violated-rule rationale.
PROCEDURES_SCHEMA = StageSchema(
    properties={
        "OD": _str_prop(),
        "OS": _str_prop(),
        "OD_reasoning": _str_prop(),
        "OS_reasoning": _str_prop(),
    },
    required=["OD", "OS", "OD_reasoning", "OS_reasoning"],
)


@dataclass
class PromptConfig:
    """Everything needed to run one staged cvar without branching in the runner.

    Only ``cvar``, ``target_columns`` and ``prompts`` differ between the
    procedure cvars; the remaining fields default to the shared bilateral shape.
    """

    cvar: str
    target_columns: list[str]
    prompts: dict[str, str]
    # JSON schema sent to the model at every stage
    schema: StageSchema = PROCEDURES_SCHEMA
    bilateral: bool = True
    label_keys: list[str] = field(default_factory=lambda: ["OD", "OS"])
    # JSON keys used for citations/reasoning on extract+revise stages
    citation_json_keys: dict[str, str] = field(
        default_factory=lambda: {"OD": "OD_reasoning", "OS": "OS_reasoning"}
    )  # label_key -> json field
    citation_label: str = "Reasoning"
    # Validation-stage reason fields
    validation_reason_keys: dict[str, str] = field(
        default_factory=lambda: {"OD": "OD_reasoning", "OS": "OS_reasoning"}
    )
    # Optional separate reasoning field (unused by the procedure cvars)
    reasoning_json_key: str | None = None
    # idx logging threshold; None = always log when verbose
    log_idx_limit: int | None = None
    # How task2 input is assembled (field names in the prompt blob)
    t2_includes_reasoning: bool = False

    def failed_labels(self) -> dict[str, str]:
        return {k: "None (failed)" for k in self.label_keys}

    def none_labels(self) -> dict[str, str]:
        return {k: "None" for k in self.label_keys}


PROMPT_REGISTRY: dict[str, PromptConfig] = {
    "prior_procedures_staged": PromptConfig(
        cvar="prior_procedures_staged",
        target_columns=[
            "Prior glaucoma surgeries or lasers OD",
            "Prior glaucoma surgeries or lasers OS",
        ],
        prompts=prompt_config.prior_procedures_staged,
    ),
    "future_procedures_staged": PromptConfig(
        cvar="future_procedures_staged",
        target_columns=[
            "Other proposed intervention OD",
            "Other proposed intervention OS",
        ],
        prompts=prompt_config.future_procedures_staged,
    ),
}


def get_prompt_config(cvar: str) -> PromptConfig:
    if cvar not in PROMPT_REGISTRY:
        raise ValueError(
            f"Unknown or out-of-scope cvar '{cvar}'. "
            f"Supported: {list(PROMPT_REGISTRY.keys())}"
        )
    return PROMPT_REGISTRY[cvar]


def list_cvars() -> list[str]:
    return list(PROMPT_REGISTRY.keys())
