from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def calculate_arbitration_state_duty(amount_rub: Decimal | float | int | str) -> int:
    """Calculate Russian commercial court state duty for property claims.

    Uses the rates introduced by Federal Law No. 259-FZ from 08.08.2024,
    effective from 08.09.2024, for Tax Code article 333.21 para. 1 subpara. 1.

    Brackets:
      <= 100 000           — 10 000 руб (fixed)
      100 001 - 1 000 000  — 10 000 + 5% of amount over 100 000
      1 000 001 - 10 000 000  — 55 000 + 3% of amount over 1 000 000
      10 000 001 - 50 000 000 — 325 000 + 1% of amount over 10 000 000
      > 50 000 000         — 725 000 + 0.5% of amount over 50 000 000, cap 10 000 000
    """

    amount = Decimal(str(amount_rub or 0))
    if amount <= 0:
        return 0
    if amount <= 100_000:
        duty = Decimal("10000")
    elif amount <= 1_000_000:
        duty = Decimal("10000") + (amount - Decimal("100000")) * Decimal("0.05")
    elif amount <= 10_000_000:
        duty = Decimal("55000") + (amount - Decimal("1000000")) * Decimal("0.03")
    elif amount <= 50_000_000:
        duty = Decimal("325000") + (amount - Decimal("10000000")) * Decimal("0.01")
    else:
        duty = Decimal("725000") + (amount - Decimal("50000000")) * Decimal("0.005")
    duty = min(duty, Decimal("10000000"))
    return int(duty.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def arbitration_state_duty_explanation(amount_rub: Decimal | float | int | str) -> str:
    amount = Decimal(str(amount_rub or 0))
    duty = calculate_arbitration_state_duty(amount)
    if amount <= 0:
        return "Цена иска не определена, госпошлина не рассчитана."
    if amount <= 100_000:
        return f"Госпошлина: {duty} руб. Фиксированная сумма для требований до 100 000 руб."
    if amount <= 1_000_000:
        extra = amount - Decimal("100000")
        return f"Госпошлина: {duty} руб. Расчет: 10 000 руб. + 5% от суммы, превышающей 100 000 руб. Превышение: {extra} руб."
    if amount <= 10_000_000:
        extra = amount - Decimal("1000000")
        return f"Госпошлина: {duty} руб. Расчет: 55 000 руб. + 3% от суммы, превышающей 1 000 000 руб. Превышение: {extra} руб."
    if amount <= 50_000_000:
        extra = amount - Decimal("10000000")
        return f"Госпошлина: {duty} руб. Расчет: 325 000 руб. + 1% от суммы, превышающей 10 000 000 руб. Превышение: {extra} руб."
    extra = amount - Decimal("50000000")
    return f"Госпошлина: {duty} руб. Расчет: 725 000 руб. + 0,5% от суммы, превышающей 50 000 000 руб., но не более 10 000 000 руб. Превышение: {extra} руб."
