from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from .config import Settings
from .company_lookup import enrich_analysis_with_rusprofile
from .claim_calculation import build_claim_calculation
from .claim_scenario import apply_claim_scenario, validate_claim_text_for_scenario
from .courts import CourtResolver
from .docx_builder import build_claim_docx, clean_claim_text
from .extraction import DocumentExtractor
from .fact_pack import build_generation_fact_pack
from .fees import arbitration_state_duty_explanation, calculate_arbitration_state_duty
from .models import ClaimContext, DocumentText
from .ocr import TesseractOcr
from .openai_client import OpenAiLegalAnalyzer
from .readiness import build_readiness_report, validate_generated_claim
from .yandex_client import YandexGptLegalAnalyzer
from .reconciliation import apply_reconciliation_balance
from .storage import CaseStorage

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[int, str], None]


class ClaimPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage = CaseStorage(settings.cases_dir, settings.training_dir)
        self.extractor = DocumentExtractor(
            TesseractOcr(settings.tesseract_cmd, timeout_seconds=settings.ocr_timeout_seconds),
            ocr_enabled=settings.ocr_enabled,
        )
        if settings.llm_provider == "yandex":
            self.ai = YandexGptLegalAnalyzer(
                api_key=settings.yandex_api_key,
                folder_id=settings.yandex_folder_id,
                model=settings.yandex_model,
                timeout_seconds=settings.openai_timeout_seconds,
                prompts_path=settings.prompts_file,
            )
        else:
            self.ai = OpenAiLegalAnalyzer(
                settings.openai_api_key,
                settings.openai_model,
                base_url=settings.openai_base_url,
                timeout_seconds=settings.openai_timeout_seconds,
                prompts_path=settings.prompts_file,
            )
        self.courts = CourtResolver(settings.courts_file)

    def run(self, input_paths: list[Path], case_name: str | None = None, progress: ProgressCallback | None = None) -> Path:
        case_id = self.analyze(input_paths, case_name=case_name, progress=progress)
        return self.generate_claim(case_id, progress=progress)

    def analyze(self, input_paths: list[Path], case_name: str | None = None, progress: ProgressCallback | None = None) -> str:
        def report(step: int, message: str) -> None:
            if progress:
                progress(step, message)

        report(1, "Создаю дело и сохраняю входные файлы")
        case_id, case_dir = self.storage.create_case_dir(case_name)
        logger.info("Created case: %s", case_id)
        copied_paths = self.storage.copy_inputs(case_dir, input_paths)

        report(2, "Извлекаю текст из документов: PDF/DOCX/XLSX, при необходимости запускаю OCR")
        documents = self.extractor.extract_many(copied_paths)
        self.storage.save_extracted_texts(case_dir, documents)

        report(2, "Отправляю извлеченный текст в ИИ для юридического анализа")
        payload = self._build_documents_payload(documents)
        analysis = self.ai.analyze_documents(payload)
        analysis = apply_reconciliation_balance(analysis, documents)
        analysis = apply_claim_scenario(analysis)
        if self.settings.rusprofile_enabled:
            report(2, "Дополняю реквизиты компаний по ИНН через Rusprofile")
            analysis = enrich_analysis_with_rusprofile(
                analysis,
                timeout_seconds=self.settings.rusprofile_timeout_seconds,
            )
        build_claim_calculation(analysis)
        self.storage.save_json(case_dir, "analysis.json", analysis)

        report(3, "Определяю суд, цену иска и рассчитываю госпошлину для проверки")
        defendant = analysis.get("defendant") or {}
        analysis["generation_fact_pack"] = build_generation_fact_pack(analysis)
        court = self.courts.resolve(defendant.get("address"), defendant.get("region"))
        state_duty = self.calculate_state_duty(analysis)
        duty_explanation = self.state_duty_explanation(analysis)
        readiness = build_readiness_report(analysis, stage="analysis")
        self.storage.save_json(
            case_dir,
            "review.json",
            {
                "case_id": case_id,
                "court": court.__dict__ if court else None,
                "state_duty_rub": state_duty,
                "state_duty_calculation": duty_explanation,
                "missing": (analysis.get("sufficiency") or {}).get("missing", []),
                **readiness,
            },
        )
        report(3, "Анализ готов. Проверьте стороны, суммы и суд перед генерацией иска")
        return case_id

    def generate_claim(
        self,
        case_id: str,
        reviewed_analysis: dict[str, Any] | None = None,
        progress: ProgressCallback | None = None,
    ) -> Path:
        def report(step: int, message: str) -> None:
            if progress:
                progress(step, message)

        case_dir = self.settings.cases_dir / case_id
        if not case_dir.exists():
            raise FileNotFoundError(f"Case not found: {case_id}")

        report(4, "Формирую иск по подтвержденным данным")
        analysis = reviewed_analysis or self._read_json(case_dir / "output" / "analysis.json")
        if reviewed_analysis is not None:
            build_claim_calculation(reviewed_analysis)
            self.storage.save_json(case_dir, "analysis.reviewed.json", reviewed_analysis)
            self.storage.save_json(case_dir, "analysis.json", reviewed_analysis)

        defendant = analysis.get("defendant") or {}
        court = self.courts.resolve(defendant.get("address"), defendant.get("region"))
        state_duty = self.calculate_state_duty(analysis)
        duty_explanation = self.state_duty_explanation(analysis)

        report(4, "Генерирую проект иска через ИИ")
        claim_text = self.ai.draft_claim(
            analysis=analysis,
            court=court.__dict__ if court else None,
            state_duty_rub=state_duty,
            state_duty_calculation=duty_explanation,
        )
        claim_text = clean_claim_text(claim_text)

        report(4, "Проверяю текст иска на соответствие сценарию")
        validation_warnings = validate_claim_text_for_scenario(claim_text, analysis)

        report(4, "Запускаю самопроверку ИИ на соответствие закону")
        total = str((analysis.get("amounts") or {}).get("total", ""))
        try:
            review_result = self.ai.review_claim(
                claim_text=claim_text,
                analysis=analysis,
                state_duty_rub=state_duty,
                total=total,
            )
            if not review_result.get("claim_text_match_scenario", True):
                validation_warnings.append("ИИ-ревью: текст иска не соответствует выбранному сценарию.")
            if not review_result.get("legal_references_valid", True):
                validation_warnings.append("ИИ-ревью: обнаружены некорректные ссылки на статьи.")
            if not review_result.get("has_court_name", True):
                validation_warnings.append("ИИ-ревью: не указано наименование суда.")
            if not review_result.get("has_date_and_signature", True):
                validation_warnings.append("ИИ-ревью: отсутствует дата или подпись.")
            if not review_result.get("no_ai_tails", True):
                validation_warnings.append("ИИ-ревью: в тексте остались разговорные фразы.")
            if not review_result.get("no_fabricated_documents", True):
                validation_warnings.append("ИИ-ревью: возможно упоминание документов, которых нет в деле.")
            for error in review_result.get("errors", []):
                validation_warnings.append(f"ИИ-ревью: {error}")
        except Exception:
            logger.warning("AI self-review failed, skipping", exc_info=True)

        critical_warnings = validate_generated_claim(claim_text, analysis, validation_warnings)
        output_docx = case_dir / "output" / "claim_draft.docx"
        build_claim_docx(claim_text, output_docx)

        context = ClaimContext(
            case_id=case_id,
            documents=self._read_documents_from_texts(case_dir),
            analysis=analysis,
            court=court,
            state_duty_rub=state_duty,
            generated_claim_text=claim_text,
            missing_items=(analysis.get("sufficiency") or {}).get("missing", []),
        )
        self.storage.save_json(case_dir, "case_summary.json", self._summary(context, output_docx))
        self.storage.save_training_snapshot(context)
        readiness = build_readiness_report(
            analysis,
            stage="claim",
            generated_claim_text=claim_text,
            validation_warnings=critical_warnings,
        )
        self.storage.save_json(
            case_dir,
            "review.json",
            {
                "case_id": case_id,
                "court": court.__dict__ if court else None,
                "state_duty_rub": state_duty,
                "state_duty_calculation": duty_explanation,
                "missing": context.missing_items,
                "validation_warnings": critical_warnings,
                **readiness,
            },
        )
        logger.info("Claim draft created: %s", output_docx)
        report(4, "Проект иска готов. Можно скачать DOCX и оставить оценку")
        return output_docx

    def calculate_state_duty(self, analysis: dict[str, Any]) -> int:
        total_amount = self._amount(analysis, "total")
        if not total_amount:
            total_amount = sum(self._amount(analysis, key) for key in ("principal_debt", "penalty", "interest_395", "other"))
        return calculate_arbitration_state_duty(total_amount)

    def state_duty_explanation(self, analysis: dict[str, Any]) -> str:
        total_amount = self._amount(analysis, "total")
        if not total_amount:
            total_amount = sum(self._amount(analysis, key) for key in ("principal_debt", "penalty", "interest_395", "other"))
        return arbitration_state_duty_explanation(total_amount)

    @staticmethod
    def _build_documents_payload(documents: list[Any], max_chars_per_doc: int = 45000) -> str:
        parts = []
        for index, doc in enumerate(documents, start=1):
            text = doc.text[:max_chars_per_doc]
            parts.append(
                f"### Документ {index}: {doc.path.name}\n"
                f"Тип: {doc.kind}; OCR: {'да' if doc.used_ocr else 'нет'}\n"
                f"{text}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _amount(analysis: dict[str, Any], key: str) -> float:
        amounts = analysis.get("amounts") or {}
        try:
            return float(str(amounts.get(key, 0)).replace(" ", "").replace(",", "."))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        import json

        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _read_documents_from_texts(case_dir: Path) -> list[Any]:
        text_dir = case_dir / "output" / "texts"
        documents = []
        if not text_dir.exists():
            return documents
        for path in sorted(text_dir.glob("*.txt")):
            documents.append(DocumentText(path=path, kind="extracted_text", text=path.read_text(encoding="utf-8"), used_ocr=False))
        return documents

    @staticmethod
    def _summary(context: ClaimContext, output_docx: Path) -> dict[str, Any]:
        sufficiency = context.analysis.get("sufficiency") or {}
        return {
            "case_id": context.case_id,
            "output_docx": str(output_docx),
            "enough_for_claim": sufficiency.get("enough"),
            "missing": context.missing_items,
            "court": context.court.__dict__ if context.court else None,
            "state_duty_rub": context.state_duty_rub,
        }
