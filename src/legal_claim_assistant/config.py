from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs) -> None:
        return None


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    openai_api_key: str
    openai_model: str
    openai_base_url: str | None
    openai_timeout_seconds: float
    yandex_api_key: str
    yandex_folder_id: str
    yandex_model: str
    tesseract_cmd: str | None
    ocr_enabled: bool
    ocr_timeout_seconds: int
    cases_dir: Path
    training_dir: Path
    courts_file: Path
    log_file: Path
    prompts_file: Path
    rusprofile_enabled: bool
    rusprofile_timeout_seconds: int


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if not raw:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "да"}


def _read_simple_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _env(name: str, values: dict[str, str], default: str = "") -> str:
    raw = os.getenv(name)
    if raw:
        return raw
    return values.get(name, default)


def _float_value(raw: str | None, default: float) -> float:
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_value(raw: str | None, default: int) -> int:
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _bool_value(raw: str | None, default: bool) -> bool:
    if not raw:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "да"}


def _default_tesseract_cmd(values: dict[str, str]) -> str | None:
    configured = _env("TESSERACT_CMD", values)
    if configured:
        return configured
    for candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def load_settings() -> Settings:
    load_dotenv(override=True)
    root = Path.cwd()
    env_values = _read_simple_env(root / ".env")
    provider = _env("LLM_PROVIDER", env_values, "openai").strip().lower()
    return Settings(
        llm_provider=provider,
        openai_api_key=_env("OPENAI_API_KEY", env_values),
        openai_model=_env("OPENAI_MODEL", env_values, "gpt-4.1"),
        openai_base_url=_env("OPENAI_BASE_URL", env_values) or None,
        openai_timeout_seconds=_float_value(_env("OPENAI_TIMEOUT_SECONDS", env_values), 300.0),
        yandex_api_key=_env("YANDEX_API_KEY", env_values),
        yandex_folder_id=_env("YANDEX_FOLDER_ID", env_values),
        yandex_model=_env("YANDEX_MODEL", env_values, "yandexgpt/latest"),
        tesseract_cmd=_default_tesseract_cmd(env_values),
        ocr_enabled=_bool_value(_env("OCR_ENABLED", env_values), True),
        ocr_timeout_seconds=_int_value(_env("OCR_TIMEOUT_SECONDS", env_values), 90),
        cases_dir=_resolve_path(_env("CASES_DIR", env_values, str(root / "data" / "cases")), root),
        training_dir=_resolve_path(_env("TRAINING_DIR", env_values, str(root / "data" / "training")), root),
        courts_file=_resolve_path(
            _env("COURTS_FILE", env_values, str(root / "data" / "references" / "arbitration_courts_ru.json")),
            root,
        ),
        log_file=root / "logs" / "assistant.log",
        prompts_file=_resolve_path(_env("PROMPTS_FILE", env_values, str(root / "data" / "prompts.json")), root),
        rusprofile_enabled=_bool_value(_env("RUSPROFILE_ENABLED", env_values), True),
        rusprofile_timeout_seconds=_int_value(_env("RUSPROFILE_TIMEOUT_SECONDS", env_values), 15),
    )


def _resolve_path(raw: str, root: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return root / path
