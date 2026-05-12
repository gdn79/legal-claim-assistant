from __future__ import annotations

import re
from datetime import datetime


def slugify_case_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Zа-яА-Я0-9_-]+", "-", value.strip()).strip("-")
    return cleaned[:80] or datetime.now().strftime("case-%Y%m%d-%H%M%S")


def compact_text(value: str) -> str:
    value = value.replace("\x00", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()
