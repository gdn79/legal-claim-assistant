from legal_claim_assistant.docx_builder import clean_claim_text


def test_clean_claim_text_removes_source_links_block():
    raw = """Взыскать задолженность.

Итоговая сумма к взысканию по расчету: 275 000 руб.

Ссылки на источники и нормы: ГК РФ - https://www.consultant.ru/document/cons_doc_LAW_5142/
АПК РФ - https://www.consultant.ru/document/cons_doc_LAW_37800/
"""
    cleaned = clean_claim_text(raw)
    assert "consultant.ru" not in cleaned
    assert "Ссылки на источники" not in cleaned
    assert "Итоговая сумма" in cleaned


def test_clean_claim_text_removes_standalone_urls():
    raw = "Взыскать долг.\nhttps://www.consultant.ru/document/cons_doc_LAW_5142/\nГоспошлина оплачена."
    cleaned = clean_claim_text(raw)
    assert "https://" not in cleaned
    assert "Госпошлина оплачена" in cleaned
