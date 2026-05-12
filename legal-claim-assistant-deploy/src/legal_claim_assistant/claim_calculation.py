from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .fees import arbitration_state_duty_explanation, calculate_arbitration_state_duty


AMOUNT_FIELDS = ("principal_debt", "penalty", "interest_395", "other")
DEFAULT_KEY_RATES_PATH = Path("data/references/cbr_key_rates.json")


@dataclass(frozen=True)
class RatePeriod:
    date_from: date
    date_to: date
    rate_percent: Decimal
    days: int
    amount: Decimal


def build_claim_calculation(analysis: dict[str, Any]) -> dict[str, Any]:
    amounts = analysis.setdefault("amounts", {})
    parts = {field: _money(amounts.get(field)) for field in AMOUNT_FIELDS}
    input_data = analysis.get("claim_calculation_input") or {}
    calculation_warnings: list[str] = []

    interest_input = input_data.get("interest_395") or {}
    interest_result = calculate_interest_395(
        principal=_first_present(interest_input.get("principal"), amounts.get("principal_debt")),
        date_from=interest_input.get("date_from"),
        date_to=interest_input.get("date_to"),
    )
    if interest_result["amount"] > Decimal("0"):
        parts["interest_395"] = interest_result["amount"]
        amounts["interest_395"] = str(interest_result["amount"])
    calculation_warnings.extend(interest_result["warnings"])

    penalty_input = input_data.get("penalty") or {}
    penalty_result = calculate_contract_penalty(
        principal=_first_present(penalty_input.get("principal"), amounts.get("principal_debt")),
        date_from=penalty_input.get("date_from"),
        date_to=penalty_input.get("date_to"),
        rate_percent_per_day=penalty_input.get("rate_percent_per_day"),
    )
    if penalty_result["amount"] > Decimal("0"):
        parts["penalty"] = penalty_result["amount"]
        amounts["penalty"] = str(penalty_result["amount"])
    calculation_warnings.extend(penalty_result["warnings"])

    declared_total = _money(amounts.get("total"))
    calculated_total = sum(parts.values(), Decimal("0"))
    total = calculated_total if interest_result["amount"] > 0 or penalty_result["amount"] > 0 else declared_total if declared_total > 0 else calculated_total
    amounts["total"] = str(total)

    warnings: list[str] = list(calculation_warnings)
    if parts["interest_395"] > 0 and not _has_period(analysis):
        warnings.append("Заявлены проценты по ст. 395 ГК РФ, но не найден период расчета.")
    if parts["penalty"] > 0 and not _has_penalty_basis(analysis):
        warnings.append("Заявлена неустойка, но нужно проверить договорное условие и период просрочки.")
    if total <= 0:
        warnings.append("Цена иска не определена.")

    calculation = {
        "parts": {key: str(value) for key, value in parts.items()},
        "declared_total": str(declared_total),
        "calculated_total": str(calculated_total),
        "total": str(total),
        "state_duty_rub": calculate_arbitration_state_duty(total),
        "state_duty_calculation": arbitration_state_duty_explanation(total),
        "interest_395": _serialize_calc_result(interest_result),
        "penalty": _serialize_calc_result(penalty_result),
        "warnings": warnings,
    }
    analysis["claim_calculation"] = calculation
    return calculation


def calculate_interest_395(
    *,
    principal: Any,
    date_from: Any,
    date_to: Any,
    key_rates_path: Path = DEFAULT_KEY_RATES_PATH,
) -> dict[str, Any]:
    principal_value = _money(principal)
    start = _parse_date(date_from)
    end = _parse_date(date_to)
    warnings: list[str] = []
    if principal_value <= 0 or not start or not end:
        return {"amount": Decimal("0"), "periods": [], "warnings": warnings}
    if end < start:
        return {"amount": Decimal("0"), "periods": [], "warnings": ["Дата окончания расчета процентов раньше даты начала."]}

    rates = load_key_rates(key_rates_path)
    if not rates:
        return {"amount": Decimal("0"), "periods": [], "warnings": ["Нет локальной таблицы ключевых ставок ЦБ РФ."]}

    periods = _split_by_rates(start, end, principal_value, rates)
    amount = sum((period.amount for period in periods), Decimal("0")).quantize(Decimal("0.01"))
    return {"amount": amount, "periods": periods, "warnings": warnings}


def calculate_contract_penalty(
    *,
    principal: Any,
    date_from: Any,
    date_to: Any,
    rate_percent_per_day: Any,
) -> dict[str, Any]:
    principal_value = _money(principal)
    start = _parse_date(date_from)
    end = _parse_date(date_to)
    rate = _money(rate_percent_per_day)
    warnings: list[str] = []
    if principal_value <= 0 or not start or not end or rate <= 0:
        return {"amount": Decimal("0"), "periods": [], "warnings": warnings}
    if end < start:
        return {"amount": Decimal("0"), "periods": [], "warnings": ["Дата окончания расчета неустойки раньше даты начала."]}
    days = (end - start).days + 1
    amount = (principal_value * rate / Decimal("100") * Decimal(days)).quantize(Decimal("0.01"))
    period = RatePeriod(start, end, rate, days, amount)
    return {"amount": amount, "periods": [period], "warnings": warnings}


def load_key_rates(path: Path = DEFAULT_KEY_RATES_PATH) -> list[tuple[date, Decimal]]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    rates: list[tuple[date, Decimal]] = []
    for item in raw:
        item_date = _parse_date(item.get("date"))
        rate = _money(item.get("rate"))
        if item_date and rate > 0:
            rates.append((item_date, rate))
    return sorted(rates, key=lambda item: item[0])


def _money(value: Any) -> Decimal:
    try:
        normalized = str(value or 0).replace(" ", "").replace("\xa0", "").replace(",", ".")
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    match = re.search(r"(\d{2})[.\-/](\d{2})[.\-/](\d{4})", text)
    if match:
        return datetime.strptime(".".join(match.groups()), "%d.%m.%Y").date()
    return None


def _split_by_rates(start: date, end: date, principal: Decimal, rates: list[tuple[date, Decimal]]) -> list[RatePeriod]:
    result: list[RatePeriod] = []
    current = start
    while current <= end:
        rate = _rate_for_day(current, rates)
        next_change = next((rate_date for rate_date, _ in rates if rate_date > current), None)
        period_end = min(end, (next_change - timedelta(days=1)) if next_change else end)
        days = (period_end - current).days + 1
        amount = (principal * Decimal(days) * rate / Decimal("100") / Decimal("365")).quantize(Decimal("0.01"))
        result.append(RatePeriod(current, period_end, rate, days, amount))
        current = period_end + timedelta(days=1)
    return result


def _rate_for_day(day: date, rates: list[tuple[date, Decimal]]) -> Decimal:
    applicable = rates[0][1]
    for rate_date, rate in rates:
        if rate_date <= day:
            applicable = rate
        else:
            break
    return applicable


def _serialize_calc_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "amount": str(result.get("amount") or "0"),
        "periods": [
            {
                "date_from": period.date_from.isoformat(),
                "date_to": period.date_to.isoformat(),
                "rate_percent": str(period.rate_percent),
                "days": period.days,
                "amount": str(period.amount),
            }
            for period in result.get("periods", [])
        ],
        "warnings": list(result.get("warnings") or []),
    }


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _has_period(analysis: dict[str, Any]) -> bool:
    text = str(analysis).lower()
    return any(token in text for token in ("период", "с ", "по ", "дата начала", "дата окончания", "просроч"))


def _has_penalty_basis(analysis: dict[str, Any]) -> bool:
    text = str(analysis).lower()
    return "неустой" in text and any(token in text for token in ("договор", "пункт", "п.", "%", "процент"))
