from legal_claim_assistant.claim_scenario import apply_claim_scenario
from legal_claim_assistant.readiness import build_readiness_report, validate_generated_claim


def test_reconciliation_scenario_has_model_requirements():
    analysis = {
        "claimant": {"name": "ООО РК Строй", "inn": "9705056778", "ogrn": "5157746183931", "address": "Москва"},
        "defendant": {"name": "ООО Главлабгрупп", "inn": "7724484743", "ogrn": "1197746472802", "address": "Москва"},
        "contracts": [{"number": "1", "date": "01.01.2024", "subject": "услуги"}],
        "payments": [{"number": "10", "amount": "100000"}],
        "amounts": {"principal_debt": 100000, "total": 100000},
        "party_reasoning": {"reconciliation_balance": {"creditor_name": "ООО РК Строй", "amount": "100000"}},
        "sufficiency": {"missing": []},
    }
    apply_claim_scenario(analysis)
    report = build_readiness_report(analysis, stage="analysis")
    assert analysis["claim_scenario"]["code"] == "reconciliation_balance"
    assert any(item["key"] == "scenario_documents" for item in report["checklist"])


def test_customer_refund_blocks_wrong_executor_fabula():
    analysis = {"claim_scenario": {"code": "customer_refund"}}
    warnings = validate_generated_claim("Истец выполнил работы, а ответчик не оплатил их.", analysis, [])
    assert warnings
