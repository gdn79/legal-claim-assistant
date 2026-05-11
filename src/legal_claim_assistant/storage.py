from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import ClaimContext, DocumentText
from .utils import slugify_case_name


class CaseStorage:
    def __init__(self, cases_dir: Path, training_dir: Path) -> None:
        self.cases_dir = cases_dir
        self.training_dir = training_dir
        self.cases_dir.mkdir(parents=True, exist_ok=True)
        self.training_dir.mkdir(parents=True, exist_ok=True)

    def create_case_dir(self, case_name: str | None) -> tuple[str, Path]:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        case_id = f"{timestamp}-{slugify_case_name(case_name or 'claim')}"
        case_dir = self.cases_dir / case_id
        (case_dir / "input").mkdir(parents=True, exist_ok=True)
        (case_dir / "output").mkdir(parents=True, exist_ok=True)
        return case_id, case_dir

    def copy_inputs(self, case_dir: Path, paths: list[Path]) -> list[Path]:
        copied: list[Path] = []
        for path in paths:
            target = case_dir / "input" / path.name
            shutil.copy2(path, target)
            copied.append(target)
        return copied

    def save_extracted_texts(self, case_dir: Path, documents: list[DocumentText]) -> None:
        text_dir = case_dir / "output" / "texts"
        text_dir.mkdir(exist_ok=True)
        for doc in documents:
            safe_name = doc.path.stem[:80] + ".txt"
            (text_dir / safe_name).write_text(doc.text, encoding="utf-8")

    def save_json(self, case_dir: Path, filename: str, data: Any) -> None:
        (case_dir / "output" / filename).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save_training_snapshot(self, context: ClaimContext) -> None:
        target = self.training_dir / f"{context.case_id}.json"
        target.write_text(
            json.dumps(
                {
                    "case_id": context.case_id,
                    "analysis": context.analysis,
                    "court": context.court.__dict__ if context.court else None,
                    "state_duty_rub": context.state_duty_rub,
                    "missing_items": context.missing_items,
                    "generated_claim_text": context.generated_claim_text,
                    "documents": [
                        {
                            "path": str(doc.path),
                            "kind": doc.kind,
                            "used_ocr": doc.used_ocr,
                            "text": doc.text,
                        }
                        for doc in context.documents
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def add_feedback(self, case_id: str, feedback_text: str, accepted: bool | None = None) -> Path:
        target = self.training_dir / f"{case_id}.feedback.json"
        payload = {
            "case_id": case_id,
            "accepted": accepted,
            "feedback": feedback_text,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target
