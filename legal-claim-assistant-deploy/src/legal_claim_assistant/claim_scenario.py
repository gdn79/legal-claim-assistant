from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


SCENARIO_LABELS = {
    "contractor_payment": "Исполнитель взыскивает оплату за работы/услуги",
    "supply_payment": "Поставщик взыскивает оплату за товар",
    "lease_debt": "Арендодатель взыскивает арендную задолженность",
    "reconciliation_balance": "Взыскание задолженности по акту сверки",
    "customer_refund": "Заказчик взыскивает переплату / возврат денег",
    "advance_return": "Возврат аванса при отсутствии исполнения",
    "unjust_enrichment": "Взыскание неосновательного обогащения",
    "penalty_only": "Взыскание договорной неустойки",
    "interest_395_only": "Взыскание процентов по ст. 395 ГК РФ",
    "generic_debt": "Взыскание задолженности",
}


SCENARIO_INSTRUCTIONS = {
    "contractor_payment": (
        "Фабула: истец выполнил работы или оказал услуги, ответчик как заказчик обязан оплатить результат. "
        "Можно описывать неоплату выполненных работ ответчиком."
    ),
    "supply_payment": (
        "Фабула: истец поставил товар, ответчик принял товар и не оплатил его полностью. "
        "Опирайся на договор поставки, УПД, накладные, счета, платежи и расчет задолженности."
    ),
    "lease_debt": (
        "Фабула: истец передал имущество в аренду, ответчик пользовался им и не внес арендную плату. "
        "Опирайся на договор аренды, акты передачи/возврата, расчет периодов и оплат."
    ),
    "reconciliation_balance": (
        "Фабула: требование основано на акте сверки и итоговом сальдо взаиморасчетов. "
        "Нельзя автоматически писать, что ответчик не оплатил выполненные истцом работы. "
        "Если истец является заказчиком по договору, иск нужно строить вокруг задолженности/переплаты, "
        "зафиксированной актом сверки, платежей и отсутствия встречного закрытия актами."
    ),
    "customer_refund": (
        "Фабула: истец как заказчик требует возврата переплаты, аванса или денежных средств, "
        "не закрытых выполненными работами. Не описывай истца как исполнителя работ."
    ),
    "advance_return": (
        "Фабула: истец перечислил аванс, но ответчик не предоставил встречное исполнение или не подтвердил его "
        "закрывающими документами. Требование строится вокруг возврата аванса и процентов при наличии расчета."
    ),
    "unjust_enrichment": (
        "Фабула: ответчик получил или удерживает денежные средства без достаточного правового основания. "
        "Не подменяй это взысканием оплаты работ, если работа/поставка не подтверждены."
    ),
    "penalty_only": (
        "Фабула: основной долг оплачен или заявляется отдельно, а текущий иск направлен на взыскание договорной "
        "неустойки. Нужны договорное условие о неустойке, период просрочки и расчет."
    ),
    "interest_395_only": (
        "Фабула: взыскиваются проценты по ст. 395 ГК РФ за пользование чужими денежными средствами. "
        "Нужны сумма долга, период просрочки, дата начала и окончания расчета."
    ),
    "generic_debt": (
        "Фабула: взыскание денежной задолженности по представленным документам. "
        "Не делай вывод о неоплате работ без проверки ролей сторон."
    ),
}


SCENARIO_REQUIREMENTS = {
    "contractor_payment": {
        "required": ["договор", "акт/УПД/накладная или иной закрывающий документ", "расчет задолженности"],
        "recommended": ["претензия", "доказательства направления претензии", "платежные документы", "доверенность/полномочия"],
    },
    "supply_payment": {
        "required": ["договор или счет/заказ", "УПД или товарная накладная", "расчет задолженности"],
        "recommended": ["претензия", "доказательства направления претензии", "сверка расчетов", "платежные документы"],
    },
    "lease_debt": {
        "required": ["договор аренды", "акт передачи или доказательства пользования", "расчет задолженности по периодам"],
        "recommended": ["претензия", "доказательства направления претензии", "платежные документы", "акт сверки"],
    },
    "reconciliation_balance": {
        "required": ["акт сверки с итоговым сальдо", "договор или основание расчетов", "расшифровка платежей/закрывающих документов"],
        "recommended": ["претензия", "доказательства направления претензии", "платежные поручения", "полномочия подписантов акта сверки"],
    },
    "customer_refund": {
        "required": ["договор", "платежные документы истца", "доказательства отсутствия встречного исполнения или акт сверки"],
        "recommended": ["претензия", "доказательства направления претензии", "расчет процентов по ст. 395 ГК РФ"],
    },
    "advance_return": {
        "required": ["договор/счет", "платежное поручение на аванс", "доказательства отсутствия исполнения или расторжения"],
        "recommended": ["претензия", "доказательства направления претензии", "расчет процентов по ст. 395 ГК РФ"],
    },
    "unjust_enrichment": {
        "required": ["доказательство перечисления или получения имущества", "обоснование отсутствия правового основания", "расчет суммы"],
        "recommended": ["претензия", "доказательства направления претензии", "переписка сторон", "банковская выписка"],
    },
    "penalty_only": {
        "required": ["договорное условие о неустойке", "период просрочки", "расчет неустойки"],
        "recommended": ["доказательство основного обязательства", "претензия", "доказательства направления претензии"],
    },
    "interest_395_only": {
        "required": ["сумма основного долга", "дата начала просрочки", "дата окончания расчета", "расчет процентов"],
        "recommended": ["документы, подтверждающие основной долг", "претензия", "доказательства направления претензии"],
    },
    "generic_debt": {
        "required": ["договор или иное основание", "документы, подтверждающие долг", "расчет задолженности"],
        "recommended": ["претензия", "доказательства направления претензии", "платежные документы"],
    },
}


@dataclass(frozen=True)
class ClaimScenario:
    code: str
    label: str
    instruction: str
    reason: str


def apply_claim_scenario(analysis: dict[str, Any]) -> dict[str, Any]:
    scenario = detect_claim_scenario(analysis)
    analysis["claim_scenario"] = {
        "code": scenario.code,
        "label": scenario.label,
        "instruction": scenario.instruction,
        "reason": scenario.reason,
    }
    return analysis


def detect_claim_scenario(analysis: dict[str, Any]) -> ClaimScenario:
    reasoning = analysis.get("party_reasoning") or {}
    balance = reasoning.get("reconciliation_balance") or {}
    if balance:
        return _scenario(
            "reconciliation_balance",
            f"Акт сверки содержит итоговое сальдо в пользу {balance.get('creditor_name', 'истца')} "
            f"на сумму {balance.get('amount', '')}.",
        )

    claimant = analysis.get("claimant") or {}
    defendant = analysis.get("defendant") or {}
    contracts = analysis.get("contracts") or []
    claim_type = str(analysis.get("claim_type") or "")
    legal_text = " ".join(str(item) for item in analysis.get("legal_basis") or [])
    text = " ".join(str(contract.get("notes", "")) for contract in contracts if isinstance(contract, dict))
    combined = " ".join([claim_type, legal_text, text]).lower()
    claimant_name = str(claimant.get("name", ""))
    defendant_name = str(defendant.get("name", ""))

    if "постав" in combined or "товар" in combined or "упд" in combined or "накладн" in combined:
        return _scenario("supply_payment", "В анализе обнаружены признаки поставки товара/УПД/накладных.")
    if "аренд" in combined:
        return _scenario("lease_debt", "В анализе обнаружены признаки арендных отношений.")
    if "неоснователь" in combined:
        return _scenario("unjust_enrichment", "В анализе указано неосновательное обогащение.")
    if "аванс" in combined or "предоплат" in combined:
        return _scenario("advance_return", "В анализе обнаружен аванс/предоплата.")
    if "неустойк" in combined and not _amount(analysis, "principal_debt"):
        return _scenario("penalty_only", "Заявляется неустойка без основного долга.")
    if "395" in combined and not _amount(analysis, "principal_debt"):
        return _scenario("interest_395_only", "Заявляются проценты по ст. 395 ГК РФ без основного долга.")

    claimant_is_customer = _party_has_role(claimant_name, "заказчик", text)
    defendant_is_executor = _party_has_role(defendant_name, "исполнитель", text)
    if claimant_is_customer and defendant_is_executor:
        return _scenario("customer_refund", "Истец похож на заказчика, а ответчик на исполнителя по договору.")

    claimant_is_executor = _party_has_role(claimant_name, "исполнитель", text)
    defendant_is_customer = _party_has_role(defendant_name, "заказчик", text)
    if claimant_is_executor and defendant_is_customer:
        return _scenario("contractor_payment", "Истец похож на исполнителя, а ответчик на заказчика по договору.")

    return _scenario("generic_debt", "Специальная модель не определена надежно.")


def scenario_instruction(code: str) -> str:
    return SCENARIO_INSTRUCTIONS.get(code, SCENARIO_INSTRUCTIONS["generic_debt"])


def scenario_requirements(code: str) -> dict[str, list[str]]:
    return SCENARIO_REQUIREMENTS.get(code, SCENARIO_REQUIREMENTS["generic_debt"])


def validate_claim_text_for_scenario(claim_text: str, analysis: dict[str, Any]) -> list[str]:
    scenario = ((analysis.get("claim_scenario") or {}).get("code") or "").strip()
    claimant_name = ((analysis.get("claimant") or {}).get("name") or "").strip()
    if scenario not in {"reconciliation_balance", "customer_refund"}:
        return []

    warnings: list[str] = []
    lower = claim_text.lower()
    if re.search(r"ответчик[^.\n]{0,120}не\s+(?:исполнил\s+)?(?:оплатил|осуществил\s+оплату)", lower):
        warnings.append(
            "Текст похож на шаблон о неоплате работ ответчиком. Для акта сверки/переплаты нужна фабула о сальдо взаиморасчетов."
        )
    if claimant_name and re.search(r"истец[^.\n]{0,120}(?:выполнил|оказал)\s+(?:работ|услуг)", lower):
        warnings.append("Текст описывает истца как исполнителя работ, хотя выбран сценарий акта сверки/возврата.")
    return warnings


def _scenario(code: str, reason: str) -> ClaimScenario:
    return ClaimScenario(
        code=code,
        label=SCENARIO_LABELS[code],
        instruction=SCENARIO_INSTRUCTIONS[code],
        reason=reason,
    )


def _party_has_role(party_name: str, role: str, text: str) -> bool:
    if not party_name or not text:
        return False
    normalized_party = _normalize(party_name)
    normalized_text = _normalize(text)
    normalized_role = _normalize(role)
    return normalized_party in normalized_text and normalized_role in normalized_text


def _normalize(value: str) -> str:
    value = value.lower()
    value = value.replace("общество с ограниченной ответственностью", "")
    value = value.replace("ооо", "")
    return re.sub(r"[^а-яa-z0-9]+", "", value)


def _amount(analysis: dict[str, Any], key: str) -> float:
    amounts = analysis.get("amounts") or {}
    try:
        return float(str(amounts.get(key, 0)).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return 0.0
