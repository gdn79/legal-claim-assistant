from __future__ import annotations

import json
import logging
import threading
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .config import Settings, load_settings
from .claim_scenario import SCENARIO_INSTRUCTIONS, SCENARIO_LABELS
from .logging_setup import configure_logging
from .pipeline import ClaimPipeline
from .prompt_store import (
    DEFAULT_PROMPTS,
    PROMPT_FIELDS,
    load_prompt_set,
    reset_prompt_set,
    save_prompt_set,
    validate_prompt_values,
)
from .storage import CaseStorage

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls"}
JOBS: dict[str, dict[str, object]] = {}
JOBS_LOCK = threading.Lock()


def create_app(settings: Settings | None = None) -> Flask:
    initial_settings = settings or load_settings()
    configure_logging(initial_settings.log_file)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
    app.config["SETTINGS"] = initial_settings

    def current_settings() -> Settings:
        if settings is not None:
            return settings
        return load_settings()

    @app.get("/")
    @app.get("/bot")
    def index():
        return _render_workspace(current_settings())

    @app.get("/prompts")
    def edit_prompts():
        active_settings = current_settings()
        prompts = load_prompt_set(active_settings.prompts_file)
        return render_template(
            "prompts.html",
            prompts=prompts.__dict__,
            fields=PROMPT_FIELDS,
            defaults=DEFAULT_PROMPTS,
            saved=request.args.get("saved") == "1",
            reset=request.args.get("reset") == "1",
            errors=[],
        )

    @app.post("/prompts")
    def save_prompts():
        active_settings = current_settings()
        values = {key: request.form.get(key, "") for key in PROMPT_FIELDS}
        errors = validate_prompt_values(values)
        if errors:
            return render_template(
                "prompts.html",
                prompts=values,
                fields=PROMPT_FIELDS,
                defaults=DEFAULT_PROMPTS,
                saved=False,
                reset=False,
                errors=errors,
            ), 400
        save_prompt_set(active_settings.prompts_file, values)
        return redirect(url_for("edit_prompts", saved="1"))

    @app.post("/prompts/reset")
    def reset_prompts():
        reset_prompt_set(current_settings().prompts_file)
        return redirect(url_for("edit_prompts", reset="1"))

    @app.post("/cases")
    def create_case():
        active_settings = current_settings()
        case_name = request.form.get("case_name") or "Арбитражный иск"
        files = request.files.getlist("documents")
        valid_files = [_save_upload(active_settings, file) for file in files if _is_allowed(file)]
        if not valid_files:
            return render_template(
                "index.html",
                summary=None,
                analysis=None,
                error="Загрузите хотя бы один PDF, DOCX или XLSX-файл.",
                env=_environment_status(active_settings),
            ), 400

        try:
            case_id = ClaimPipeline(active_settings).analyze(valid_files, case_name=case_name)
        except Exception as exc:
            logger.exception("Case processing failed")
            return render_template(
                "index.html",
                summary=None,
                analysis=None,
                error=f"Ошибка обработки: {exc}",
                env=_environment_status(active_settings),
            ), 500

        return redirect(url_for("case_result", case_id=case_id))

    @app.post("/cases/jobs")
    def create_case_job():
        active_settings = current_settings()
        case_name = request.form.get("case_name") or "Арбитражный иск"
        files = request.files.getlist("documents")
        valid_files = [_save_upload(active_settings, file) for file in files if _is_allowed(file)]
        if not valid_files:
            return jsonify({"error": "Загрузите хотя бы один PDF, DOCX или XLSX-файл."}), 400

        job_id = uuid.uuid4().hex
        _set_job(
            job_id,
            state="queued",
            step=1,
            message="Файлы загружены. Обработка поставлена в очередь.",
            result_url=None,
            error=None,
        )
        worker = threading.Thread(
            target=_run_case_job,
            args=(job_id, active_settings, valid_files, case_name),
            daemon=True,
        )
        worker.start()
        return jsonify({"job_id": job_id, "status_url": url_for("case_job_status", job_id=job_id)})

    @app.get("/cases/jobs/<job_id>")
    def case_job_status(job_id: str):
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if not job:
                return jsonify({"error": "Задача не найдена"}), 404
            return jsonify(job)

    @app.get("/cases/<case_id>")
    def case_result(case_id: str):
        active_settings = current_settings()
        case_dir = active_settings.cases_dir / case_id / "output"
        if not case_dir.exists():
            abort(404)
        summary = _read_json(case_dir / "case_summary.json")
        analysis = _read_json(case_dir / "analysis.json")
        review = _read_json(case_dir / "review.json")
        if review.get("status") == "blocked":
            summary = None
        return _render_workspace(active_settings, summary=summary, analysis=analysis, review=review)

    @app.post("/cases/<case_id>/generate")
    def generate_claim(case_id: str):
        active_settings = current_settings()
        case_dir = active_settings.cases_dir / case_id / "output"
        if not case_dir.exists():
            abort(404)
        analysis = _read_json(case_dir / "analysis.json")
        reviewed_analysis = _build_reviewed_analysis(analysis, request.form)
        try:
            ClaimPipeline(active_settings).generate_claim(case_id, reviewed_analysis=reviewed_analysis)
        except Exception as exc:
            logger.exception("Claim generation failed")
            review = _read_json(case_dir / "review.json")
            return _render_workspace(
                active_settings,
                summary=None,
                analysis=reviewed_analysis,
                review=review,
                error=f"Ошибка генерации иска: {exc}",
            ), 500
        return redirect(url_for("case_result", case_id=case_id))

    @app.post("/cases/<case_id>/generate/jobs")
    def generate_claim_job(case_id: str):
        active_settings = current_settings()
        case_dir = active_settings.cases_dir / case_id / "output"
        if not case_dir.exists():
            return jsonify({"error": "Дело не найдено"}), 404
        analysis = _read_json(case_dir / "analysis.json")
        reviewed_analysis = _build_reviewed_analysis(analysis, request.form)
        job_id = uuid.uuid4().hex
        _set_job(
            job_id,
            state="queued",
            step=4,
            message="Данные подтверждены. Запускаю генерацию DOCX.",
            result_url=None,
            error=None,
        )
        worker = threading.Thread(
            target=_run_generate_job,
            args=(job_id, active_settings, case_id, reviewed_analysis),
            daemon=True,
        )
        worker.start()
        return jsonify({"job_id": job_id, "status_url": url_for("case_job_status", job_id=job_id)})

    @app.get("/cases/<case_id>/download")
    def download_claim(case_id: str):
        active_settings = current_settings()
        output_dir = active_settings.cases_dir / case_id / "output"
        review = _read_json(output_dir / "review.json")
        if review and not review.get("can_download", True):
            return _render_workspace(
                active_settings,
                summary=_read_json(output_dir / "case_summary.json"),
                analysis=_read_json(output_dir / "analysis.json"),
                review=review,
                error="DOCX сформирован, но автоматическая проверка нашла критические ошибки. Исправьте карточку дела или промпт и сформируйте документ заново.",
            ), 409
        output = output_dir / "claim_draft.docx"
        if not output.exists():
            abort(404)
        return send_file(output.resolve(), as_attachment=True, download_name="claim_draft.docx")

    @app.post("/cases/<case_id>/feedback")
    def save_feedback(case_id: str):
        active_settings = current_settings()
        feedback = request.form.get("feedback", "").strip()
        accepted_raw = request.form.get("accepted")
        accepted = None
        if accepted_raw == "true":
            accepted = True
        elif accepted_raw == "false":
            accepted = False
        if feedback:
            CaseStorage(active_settings.cases_dir, active_settings.training_dir).add_feedback(case_id, feedback, accepted)
        return redirect(url_for("case_result", case_id=case_id))

    return app


def _render_workspace(
    settings: Settings,
    summary: dict | None = None,
    analysis: dict | None = None,
    review: dict | None = None,
    error: str | None = None,
):
    return render_template(
        "index.html",
        summary=summary,
        analysis=analysis,
        review=review,
        error=error,
        env=_environment_status(settings),
        scenario_labels=SCENARIO_LABELS,
    )


def _environment_status(settings: Settings) -> dict[str, object]:
    return {
        "openai_configured": bool(settings.openai_api_key),
        "tesseract_configured": bool(settings.tesseract_cmd),
        "ocr_enabled": settings.ocr_enabled,
        "openai_timeout_seconds": settings.openai_timeout_seconds,
        "ocr_timeout_seconds": settings.ocr_timeout_seconds,
        "cases_dir": str(settings.cases_dir),
        "training_dir": str(settings.training_dir),
        "rusprofile_enabled": settings.rusprofile_enabled,
    }


def _set_job(job_id: str, **values: object) -> None:
    with JOBS_LOCK:
        current = JOBS.setdefault(job_id, {})
        current.update(values)


def _run_case_job(job_id: str, settings: Settings, input_paths: list[Path], case_name: str) -> None:
    def progress(step: int, message: str) -> None:
        _set_job(job_id, state="running", step=step, message=message)

    try:
        progress(1, "Запускаю обработку документов")
        case_id = ClaimPipeline(settings).analyze(input_paths, case_name=case_name, progress=progress)
        _set_job(
            job_id,
            state="completed",
            step=3,
            message="Анализ готов. Проверьте данные перед генерацией иска.",
            result_url=f"/cases/{case_id}",
            case_id=case_id,
        )
    except Exception as exc:
        logger.exception("Case job failed: %s", job_id)
        _set_job(
            job_id,
            state="failed",
            step=2,
            message="Обработка остановлена из-за ошибки.",
            error=f"Ошибка обработки: {exc}",
        )


def _run_generate_job(job_id: str, settings: Settings, case_id: str, reviewed_analysis: dict) -> None:
    def progress(step: int, message: str) -> None:
        _set_job(job_id, state="running", step=step, message=message)

    try:
        progress(4, "Генерирую проект иска через ИИ")
        ClaimPipeline(settings).generate_claim(case_id, reviewed_analysis=reviewed_analysis, progress=progress)
        _set_job(
            job_id,
            state="completed",
            step=4,
            message="DOCX готов. Открываю результат.",
            result_url=f"/cases/{case_id}",
            case_id=case_id,
        )
    except Exception as exc:
        logger.exception("Generation job failed: %s", job_id)
        _set_job(
            job_id,
            state="failed",
            step=4,
            message="Генерация остановлена из-за ошибки.",
            error=f"Ошибка генерации иска: {exc}",
        )


def _is_allowed(file: FileStorage) -> bool:
    if not file or not file.filename:
        return False
    return Path(file.filename).suffix.lower() in ALLOWED_EXTENSIONS


def _save_upload(settings: Settings, file: FileStorage) -> Path:
    upload_dir = settings.cases_dir / "_uploads" / uuid.uuid4().hex
    upload_dir.mkdir(parents=True, exist_ok=True)
    original_suffix = Path(file.filename or "").suffix.lower()
    filename = secure_filename(file.filename or "document")
    if not filename or not Path(filename).suffix:
        stem = filename or "document"
        if stem.lower() == original_suffix.lstrip("."):
            stem = "document"
        filename = f"{stem}{original_suffix}"
    target = upload_dir / filename
    file.save(target)
    logger.info("Uploaded file saved: %s", target)
    return target


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _build_reviewed_analysis(analysis: dict, form) -> dict:
    reviewed = json.loads(json.dumps(analysis, ensure_ascii=False))
    reviewed["claim_type"] = form.get("claim_type", reviewed.get("claim_type", "")).strip()
    scenario_code = form.get("claim_scenario_code", ((reviewed.get("claim_scenario") or {}).get("code") or "generic_debt")).strip()
    if scenario_code not in SCENARIO_LABELS:
        scenario_code = "generic_debt"
    reviewed["claim_scenario"] = {
        "code": scenario_code,
        "label": SCENARIO_LABELS[scenario_code],
        "instruction": SCENARIO_INSTRUCTIONS[scenario_code],
        "reason": form.get("claim_scenario_reason", ((reviewed.get("claim_scenario") or {}).get("reason") or "")).strip(),
    }

    claimant = reviewed.setdefault("claimant", {})
    claimant["name"] = form.get("claimant_name", claimant.get("name", "")).strip()
    claimant["inn"] = form.get("claimant_inn", claimant.get("inn", "")).strip()
    claimant["ogrn"] = form.get("claimant_ogrn", claimant.get("ogrn", "")).strip()
    claimant["kpp"] = form.get("claimant_kpp", claimant.get("kpp", "")).strip()
    claimant["representative"] = form.get("claimant_representative", claimant.get("representative", "")).strip()
    claimant["address"] = form.get("claimant_address", claimant.get("address", "")).strip()

    defendant = reviewed.setdefault("defendant", {})
    defendant["name"] = form.get("defendant_name", defendant.get("name", "")).strip()
    defendant["inn"] = form.get("defendant_inn", defendant.get("inn", "")).strip()
    defendant["ogrn"] = form.get("defendant_ogrn", defendant.get("ogrn", "")).strip()
    defendant["kpp"] = form.get("defendant_kpp", defendant.get("kpp", "")).strip()
    defendant["representative"] = form.get("defendant_representative", defendant.get("representative", "")).strip()
    defendant["address"] = form.get("defendant_address", defendant.get("address", "")).strip()
    defendant["region"] = form.get("defendant_region", defendant.get("region", "")).strip()

    amounts = reviewed.setdefault("amounts", {})
    for key in ("principal_debt", "penalty", "interest_395", "other", "total"):
        amounts[key] = form.get(f"amount_{key}", amounts.get(key, "")).strip()

    calc_input = reviewed.setdefault("claim_calculation_input", {})
    interest_input = calc_input.setdefault("interest_395", {})
    interest_input["principal"] = form.get("interest_395_principal", interest_input.get("principal", amounts.get("principal_debt", ""))).strip()
    interest_input["date_from"] = form.get("interest_395_date_from", interest_input.get("date_from", "")).strip()
    interest_input["date_to"] = form.get("interest_395_date_to", interest_input.get("date_to", "")).strip()
    penalty_input = calc_input.setdefault("penalty", {})
    penalty_input["principal"] = form.get("penalty_principal", penalty_input.get("principal", amounts.get("principal_debt", ""))).strip()
    penalty_input["date_from"] = form.get("penalty_date_from", penalty_input.get("date_from", "")).strip()
    penalty_input["date_to"] = form.get("penalty_date_to", penalty_input.get("date_to", "")).strip()
    penalty_input["rate_percent_per_day"] = form.get("penalty_rate_percent_per_day", penalty_input.get("rate_percent_per_day", "")).strip()

    contracts = reviewed.setdefault("contracts", [])
    if contracts and isinstance(contracts[0], dict):
        contracts[0]["number"] = form.get("contract_number", contracts[0].get("number", "")).strip()
        contracts[0]["date"] = form.get("contract_date", contracts[0].get("date", "")).strip()
        contracts[0]["subject"] = form.get("contract_subject", contracts[0].get("subject", "")).strip()
    elif form.get("contract_number") or form.get("contract_date") or form.get("contract_subject"):
        contracts.append({
            "number": form.get("contract_number", "").strip(),
            "date": form.get("contract_date", "").strip(),
            "subject": form.get("contract_subject", "").strip(),
        })

    sufficiency = reviewed.setdefault("sufficiency", {})
    missing_raw = form.get("missing_items", "")
    sufficiency["missing"] = [line.strip() for line in missing_raw.splitlines() if line.strip()]
    sufficiency["enough"] = form.get("enough_for_claim") == "true"
    return reviewed
