from __future__ import annotations

import json
import logging
from typing import Any

from openai import APIStatusError, APITimeoutError
from openai import OpenAI

from .prompts import REVIEW_SYSTEM_PROMPT, REVIEW_USER_PROMPT
from .prompt_store import PromptSet, load_prompt_set

logger = logging.getLogger(__name__)


class OpenAiLegalAnalyzer:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout_seconds: float = 120.0,
        prompts_path=None,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set. Create .env from .env.example.")
        base_url = self._normalize_base_url(base_url)
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.prompts: PromptSet = load_prompt_set(prompts_path)

    def analyze_documents(self, documents_payload: str) -> dict[str, Any]:
        logger.info("Sending documents to OpenAI for legal analysis")
        text = self._respond(
            system=self.prompts.analysis_system,
            user=self.prompts.analysis_user.replace("{documents}", documents_payload),
        )
        return self._load_json(text)

    def draft_claim(
        self,
        analysis: dict[str, Any],
        court: dict[str, Any] | None,
        state_duty_rub: int | None,
        state_duty_calculation: str = "",
    ) -> str:
        logger.info("Sending analyzed data to OpenAI for claim drafting")
        return self._respond(
            system=self.prompts.claim_system,
            user=self.prompts.claim_user.format(
                analysis=json.dumps(analysis, ensure_ascii=False, indent=2),
                court=json.dumps(court or {}, ensure_ascii=False, indent=2),
                state_duty_rub=state_duty_rub or 0,
                state_duty_calculation=state_duty_calculation,
            ),
        )

    def _respond(self, system: str, user: str) -> str:
        logger.info(
            "OpenAI request started: model=%s base_url=%s timeout=%ss",
            self.model,
            self.base_url or "default",
            self.timeout_seconds,
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except APIStatusError as exc:
            if exc.status_code == 404:
                raise RuntimeError(
                    f"Модель '{self.model}' не найдена у API-провайдера. "
                    "Проверьте OPENAI_MODEL в .env и укажите точное имя модели из кабинета Artemox."
                ) from exc
            raise
        except APITimeoutError as exc:
            raise TimeoutError(
                f"API не ответил за {self.timeout_seconds} секунд. "
                "Увеличьте OPENAI_TIMEOUT_SECONDS в .env, выберите более быструю модель "
                "или уменьшите количество/объем загруженных документов."
            ) from exc
        logger.info("OpenAI request finished")
        content = response.choices[0].message.content or ""
        if not content.strip():
            logger.warning("OpenAI returned empty response")
        return content.strip()

    def review_claim(
        self,
        claim_text: str,
        analysis: dict[str, Any],
        state_duty_rub: int | None,
        total: str = "",
    ) -> dict[str, Any]:
        scenario = analysis.get("claim_scenario") or {}
        claimant = analysis.get("claimant") or {}
        defendant = analysis.get("defendant") or {}
        fact_pack = analysis.get("generation_fact_pack") or {}
        user = REVIEW_USER_PROMPT.format(
            claim_text=claim_text,
            scenario_label=scenario.get("label", ""),
            claimant_name=claimant.get("name", ""),
            claimant_role=fact_pack.get("claimant_role", "истец"),
            defendant_name=defendant.get("name", ""),
            defendant_role=fact_pack.get("defendant_role", "ответчик"),
            total=total or "не указана",
            state_duty_rub=state_duty_rub or 0,
        )
        text = self._respond(system=REVIEW_SYSTEM_PROMPT, user=user)
        return self._load_json(text)

    @staticmethod
    def _normalize_base_url(base_url: str | None) -> str | None:
        if not base_url:
            return None
        normalized = base_url.rstrip("/")
        suffix = "/chat/completions"
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
        return normalized

    @staticmethod
    def _load_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.removeprefix("json").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"OpenAI returned non-JSON analysis: {text[:1000]}") from exc
