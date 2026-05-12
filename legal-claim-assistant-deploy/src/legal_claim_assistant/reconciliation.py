from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .models import DocumentText


@dataclass(frozen=True)
class ReconciliationBalance:
    creditor_name: str
    amount: float
    source: str


BALANCE_PATTERN = re.compile(
    r"задолженность\s+в\s+пользу\s+(?P<creditor>.+?)\s+(?P<amount>\d[\d\s]*[,.]\d{2})",
    re.IGNORECASE,
)


def apply_reconciliation_balance(analysis: dict[str, Any], documents: list[DocumentText]) -> dict[str, Any]:
    balance = find_reconciliation_balance(documents)
    if not balance:
        return analysis

    claimant = analysis.get("claimant") or {}
    defendant = analysis.get("defendant") or {}
    claimant_name = claimant.get("name", "")
    defendant_name = defendant.get("name", "")

    if _same_party(balance.creditor_name, claimant_name):
        _write_balance_reason(analysis, balance, swapped=False)
        return analysis

    if _same_party(balance.creditor_name, defendant_name):
        analysis["claimant"], analysis["defendant"] = defendant, claimant
        _set_amounts_from_balance(analysis, balance.amount)
        _write_balance_reason(analysis, balance, swapped=True)
        return analysis

    questions = analysis.setdefault("questions_for_user", [])
    questions.append(
        f"Акт сверки указывает задолженность в пользу {balance.creditor_name} "
        f"на сумму {balance.amount:.2f}, но сторона не совпала с распознанными участниками."
    )
    reasoning = analysis.setdefault("party_reasoning", {})
    reasoning["uncertain"] = True
    reasoning["reconciliation_balance"] = {
        "creditor_name": balance.creditor_name,
        "amount": balance.amount,
        "source": balance.source,
    }
    return analysis


def find_reconciliation_balance(documents: list[DocumentText]) -> ReconciliationBalance | None:
    for document in documents:
        if "акт сверки" not in document.text.lower() and "задолженность в пользу" not in document.text.lower():
            continue
        matches = list(BALANCE_PATTERN.finditer(document.text))
        if not matches:
            continue
        match = matches[-1]
        creditor = _clean_party_name(match.group("creditor"))
        amount = _parse_amount(match.group("amount"))
        if creditor and amount:
            return ReconciliationBalance(creditor_name=creditor, amount=amount, source=document.path.name)
    return None


def _set_amounts_from_balance(analysis: dict[str, Any], amount: float) -> None:
    amounts = analysis.setdefault("amounts", {})
    value = str(int(amount)) if amount.is_integer() else f"{amount:.2f}"
    amounts["principal_debt"] = value
    amounts["total"] = value


def _write_balance_reason(analysis: dict[str, Any], balance: ReconciliationBalance, swapped: bool) -> None:
    reasoning = analysis.setdefault("party_reasoning", {})
    reasoning["reconciliation_balance"] = {
        "creditor_name": balance.creditor_name,
        "amount": balance.amount,
        "source": balance.source,
        "swapped_parties": swapped,
    }
    reasoning["claimant_reason"] = (
        f"Акт сверки {balance.source} содержит итоговое сальдо: "
        f"задолженность в пользу {balance.creditor_name} {balance.amount:.2f}."
    )
    reasoning["defendant_reason"] = "Ответчик определен как другая сторона взаиморасчетов по акту сверки."
    reasoning["uncertain"] = False


def _clean_party_name(value: str) -> str:
    cleaned = re.split(r"\s{2,}|\|", value.strip())[0]
    cleaned = cleaned.strip(" .,:;")
    return cleaned.replace("«", '"').replace("»", '"')


def _parse_amount(value: str) -> float:
    normalized = value.replace(" ", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return 0.0


def _same_party(left: str, right: str) -> bool:
    left_norm = _normalize_party(left)
    right_norm = _normalize_party(right)
    return bool(left_norm and right_norm and (left_norm in right_norm or right_norm in left_norm))


def _normalize_party(value: str) -> str:
    normalized = value.lower()
    normalized = normalized.replace("общество с ограниченной ответственностью", "")
    normalized = normalized.replace("ооо", "")
    normalized = normalized.replace('"', "")
    normalized = normalized.replace("«", "").replace("»", "")
    normalized = re.sub(r"[^а-яa-z0-9]+", "", normalized)
    return normalized
