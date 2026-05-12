from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .prompts import ANALYSIS_SYSTEM_PROMPT, ANALYSIS_USER_PROMPT, CLAIM_SYSTEM_PROMPT, CLAIM_USER_PROMPT


PROMPT_FIELDS = {
    "analysis_system": "Системный промпт анализа",
    "analysis_user": "Пользовательский промпт анализа",
    "claim_system": "Системный промпт иска",
    "claim_user": "Пользовательский промпт иска",
}


DEFAULT_PROMPTS = {
    "analysis_system": ANALYSIS_SYSTEM_PROMPT,
    "analysis_user": ANALYSIS_USER_PROMPT,
    "claim_system": CLAIM_SYSTEM_PROMPT,
    "claim_user": CLAIM_USER_PROMPT,
}


@dataclass(frozen=True)
class PromptSet:
    analysis_system: str
    analysis_user: str
    claim_system: str
    claim_user: str


def load_prompt_set(path: Path | None = None) -> PromptSet:
    values = DEFAULT_PROMPTS.copy()
    if path and path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            saved = {}
        if isinstance(saved, dict):
            for key in DEFAULT_PROMPTS:
                value = saved.get(key)
                if isinstance(value, str) and value.strip():
                    values[key] = value
    return PromptSet(**values)


def save_prompt_set(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        key: values.get(key, DEFAULT_PROMPTS[key])
        for key in DEFAULT_PROMPTS
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def reset_prompt_set(path: Path) -> None:
    if path.exists():
        path.unlink()


def validate_prompt_values(values: dict[str, str]) -> list[str]:
    errors: list[str] = []
    analysis_user = values.get("analysis_user", "")
    claim_user = values.get("claim_user", "")
    if "{documents}" not in analysis_user:
        errors.append("В пользовательском промпте анализа должен остаться маркер {documents}.")
    for marker in ("{analysis}", "{court}", "{state_duty_rub}", "{state_duty_calculation}"):
        if marker not in claim_user:
            errors.append(f"В пользовательском промпте иска должен остаться маркер {marker}.")

    json_example = _extract_json_example(analysis_user)
    if json_example:
        try:
            json.loads(json_example)
        except json.JSONDecodeError as exc:
            errors.append(f"JSON-шаблон в промпте анализа некорректен: {exc.msg} возле позиции {exc.pos}.")
    return errors


def _extract_json_example(text: str) -> str:
    marker = "Формат JSON:"
    start = text.find(marker)
    if start == -1:
        return ""
    json_start = text.find("{", start)
    documents_start = text.find("Документы:", json_start)
    if json_start == -1:
        return ""
    candidate = text[json_start:documents_start if documents_start != -1 else len(text)].strip()
    json_end = candidate.rfind("}")
    if json_end == -1:
        return ""
    return candidate[: json_end + 1]
