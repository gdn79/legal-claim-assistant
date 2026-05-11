from legal_claim_assistant.claim_calculation import (
    build_claim_calculation,
    calculate_contract_penalty,
    calculate_interest_395,
)


def test_contract_penalty_daily_rate():
    result = calculate_contract_penalty(
        principal="100000",
        date_from="01.01.2026",
        date_to="10.01.2026",
        rate_percent_per_day="0.1",
    )
    assert str(result["amount"]) == "1000.00"


def test_interest_395_uses_key_rate_periods():
    from pathlib import Path

    rates = Path(".tmp/test_key_rates.json")
    rates.parent.mkdir(exist_ok=True)
    rates.write_text('[{"date":"2026-01-01","rate":"10"},{"date":"2026-01-06","rate":"20"}]', encoding="utf-8")
    result = calculate_interest_395(
        principal="365000",
        date_from="2026-01-01",
        date_to="2026-01-10",
        key_rates_path=rates,
    )
    assert str(result["amount"]) == "1500.00"
    assert len(result["periods"]) == 2


def test_build_claim_calculation_updates_amounts_from_manual_inputs():
    analysis = {
        "amounts": {"principal_debt": "100000", "total": "100000"},
        "claim_calculation_input": {
            "penalty": {
                "principal": "100000",
                "date_from": "01.01.2026",
                "date_to": "10.01.2026",
                "rate_percent_per_day": "0.1",
            }
        },
    }
    calculation = build_claim_calculation(analysis)
    assert calculation["parts"]["penalty"] == "1000.00"
    assert analysis["amounts"]["total"] == "101000.00"
