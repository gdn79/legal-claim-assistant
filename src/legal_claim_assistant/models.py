from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DocumentText:
    path: Path
    kind: str
    text: str
    used_ocr: bool = False


@dataclass
class CourtInfo:
    name: str
    region: str
    address: str
    website: str


@dataclass
class ClaimContext:
    case_id: str
    documents: list[DocumentText]
    analysis: dict[str, Any]
    court: CourtInfo | None = None
    state_duty_rub: int | None = None
    generated_claim_text: str | None = None
    missing_items: list[str] = field(default_factory=list)
