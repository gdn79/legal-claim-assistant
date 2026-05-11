from __future__ import annotations

from typing import Any


def build_generation_fact_pack(analysis: dict[str, Any]) -> dict[str, Any]:
    scenario = analysis.get("claim_scenario") or {}
    claimant = analysis.get("claimant") or {}
    defendant = analysis.get("defendant") or {}
    reasoning = analysis.get("party_reasoning") or {}
    balance = reasoning.get("reconciliation_balance") or {}

    pack = {
        "scenario_code": scenario.get("code") or "generic_debt",
        "scenario_label": scenario.get("label") or "",
        "claimant_role": _claimant_role(analysis),
        "defendant_role": _defendant_role(analysis),
        "claimant": claimant.get("name") or "",
        "defendant": defendant.get("name") or "",
        "reconciliation_balance": balance,
        "must_use_facts": [],
        "forbidden_phrases": [],
        "forbidden_legal_theory": [],
    }

    if pack["scenario_code"] in {"reconciliation_balance", "customer_refund", "advance_return", "unjust_enrichment"}:
        pack["must_use_facts"].extend(
            [
                f"Истец: {pack['claimant']}.",
                f"Ответчик: {pack['defendant']}.",
                "Требование строится вокруг задолженности/переплаты/сальдо, а не вокруг неоплаты работ истца.",
                "Если истец был заказчиком по договору, он не является исполнителем работ.",
            ]
        )
        if balance:
            pack["must_use_facts"].append(
                f"Акт сверки фиксирует задолженность в пользу {balance.get('creditor_name', pack['claimant'])} "
                f"на сумму {balance.get('amount', '')}."
            )
        pack["forbidden_phrases"].extend(
            [
                "истец выполнил работы",
                "истец оказал услуги",
                "ответчик не оплатил выполненные истцом работы",
                "ответчик не оплатил оказанные истцом услуги",
            ]
        )
        pack["forbidden_legal_theory"].extend(
            [
                "Не писать иск как требование исполнителя к заказчику об оплате работ.",
                "Не ссылаться на неустойку за просрочку оплаты работ, если истец является заказчиком.",
                "Не называть платежное поручение актом выполненных работ.",
            ]
        )

    return pack


def _claimant_role(analysis: dict[str, Any]) -> str:
    scenario = ((analysis.get("claim_scenario") or {}).get("code") or "")
    if scenario in {"customer_refund", "advance_return"}:
        return "заказчик/плательщик/кредитор"
    if scenario == "reconciliation_balance":
        return "кредитор по акту сверки"
    if scenario == "contractor_payment":
        return "исполнитель/подрядчик"
    if scenario == "supply_payment":
        return "поставщик"
    if scenario == "lease_debt":
        return "арендодатель"
    return "истец"


def _defendant_role(analysis: dict[str, Any]) -> str:
    scenario = ((analysis.get("claim_scenario") or {}).get("code") or "")
    if scenario in {"customer_refund", "advance_return"}:
        return "получатель денег/должник"
    if scenario == "reconciliation_balance":
        return "должник по акту сверки"
    if scenario == "contractor_payment":
        return "заказчик"
    if scenario == "supply_payment":
        return "покупатель"
    if scenario == "lease_debt":
        return "арендатор"
    return "ответчик"
