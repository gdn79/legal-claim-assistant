from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from .models import CourtInfo

logger = logging.getLogger(__name__)


class CourtResolver:
    def __init__(self, courts_file: Path) -> None:
        self.courts_file = courts_file
        self.courts = self._load()

    def _load(self) -> list[dict[str, str]]:
        if not self.courts_file.exists():
            logger.warning("Court reference file does not exist: %s", self.courts_file)
            return []
        return json.loads(self.courts_file.read_text(encoding="utf-8"))

    def resolve(self, defendant_address: str | None, defendant_region: str | None = None) -> CourtInfo | None:
        haystack = " ".join([defendant_address or "", defendant_region or ""]).lower()
        if not haystack.strip():
            return None

        for item in self.courts:
            keywords = [item.get("region", ""), *item.get("keywords", [])]
            if any(re.search(rf"\b{re.escape(keyword.lower())}\b", haystack) for keyword in keywords if keyword):
                return CourtInfo(
                    name=item["name"],
                    region=item["region"],
                    address=item.get("address", ""),
                    website=item.get("website", ""),
                )
        return None
