from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .prompt_store import PromptSet, load_prompt_set
from .prompts import REVIEW_SYSTEM_PROMPT, REVIEW_USER_PROMPT

logger = logging.getLogger(__name__)


class YandexGptLegalAnalyzer:
    BASE_URL = "https://llm.api.cloud.yandex.net/v1"

    def __init__(
        self,
        api_key: str,
        folder_id: str,
        model: str,
        timeout_seconds: float = 120.0,
        prompts_path=None,
    ) -> None:
        if not api_key:
            raise ValueError("YANDEX_API_KEY is not set. Create .env from .env.example.")
        if not folder_id:
            raise ValueError("YANDEX_FOLDER_ID is not set. Create .env from .env.example.")
        self.api_key = api_key
        self.folder_id = folder_id
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.prompts: PromptSet = load_prompt_set(prompts_path)
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Api-Key {api_key}",
                "x-folder-id": folder_id,
                "Content-Type": "application/json",
            },
            timeout=timeout_seconds,
        )

    def analyze_documents(self, documents_payload: str) -> dict[str, Any]:
        logger.info("Sending documents to YandexGPT for legal analysis")
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
        logger.info("Sending analyzed data to YandexGPT for claim drafting")
        return self._respond(
            system=self.prompts.claim_system,
            user=self.prompts.claim_user.format(
                analysis=json.dumps(analysis, ensure_ascii=False, indent=2),
                court=json.dumps(court or {}, ensure_ascii=False, indent=2),
                state_duty_rub=state_duty_rub or 0,
                state_duty_calculation=state_duty_calculation,
            ),
        )

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

    def _respond(self, system: str, user: str) -> str:
        logger.info(
            "YandexGPT request started: model=%s timeout=%ss",
            self.model,
            self.timeout_seconds,
        )
        try:
            response = self._client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": 4000,
                },
            )
        except httpx.TimeoutException as exc:
            raise TimeoutError(
                f"YandexGPT не ответил за {self.timeout_seconds} секунд. "
                "Увеличьте OPENAI_TIMEOUT_SECONDS в .env."
            ) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise RuntimeError(
                    f"Модель '{self.model}' не найдена. "
                    "Проверьте YANDEX_MODEL в .env."
                ) from exc
            if exc.response.status_code == 401:
                raise RuntimeError(
                    "YandexGPT отказал в доступе. "
                    "Проверьте YANDEX_API_KEY и YANDEX_FOLDER_ID в .env."
                ) from exc
            raise RuntimeError(
                f"YandexGPT вернул ошибку {exc.response.status_code}: {exc.response.text[:500]}"
            ) from exc

        logger.info("YandexGPT request finished")
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            logger.warning("YandexGPT returned empty response")
        return content.strip()

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _load_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.removeprefix("json").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"YandexGPT returned non-JSON response: {text[:1000]}") from exc
