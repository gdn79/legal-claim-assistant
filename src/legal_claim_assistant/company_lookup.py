from __future__ import annotations

import html
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompanyProfile:
    inn: str
    name: str = ""
    ogrn: str = ""
    kpp: str = ""
    address: str = ""
    director: str = ""
    source_url: str = ""


class RusprofileClient:
    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds

    def lookup(self, inn: str) -> CompanyProfile | None:
        inn = re.sub(r"\D", "", inn or "")
        if len(inn) not in {10, 12}:
            return None

        url = f"https://www.rusprofile.ru/search?query={inn}"
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                page_url = response.geturl()
                text = response.read().decode("utf-8", "ignore")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("Rusprofile lookup failed for INN %s: %s", inn, exc)
            return None

        profile = CompanyProfile(
            inn=inn,
            name=_extract_name(text),
            ogrn=_extract_by_id(text, "clip_ogrn"),
            kpp=_extract_by_id(text, "clip_kpp"),
            address=_extract_address(text),
            director=_extract_director(text),
            source_url=page_url,
        )
        if not any((profile.name, profile.ogrn, profile.kpp, profile.address, profile.director)):
            logger.warning("Rusprofile returned no parseable company data for INN %s", inn)
            return None
        return profile


def enrich_analysis_with_rusprofile(analysis: dict[str, Any], timeout_seconds: int = 15) -> dict[str, Any]:
    client = RusprofileClient(timeout_seconds=timeout_seconds)
    lookups: dict[str, dict[str, str]] = {}
    for role in ("claimant", "defendant"):
        party = analysis.get(role)
        if not isinstance(party, dict):
            continue
        profile = client.lookup(str(party.get("inn", "")))
        if not profile:
            continue
        _fill_missing_party_fields(party, profile)
        lookups[role] = {
            "inn": profile.inn,
            "name": profile.name,
            "ogrn": profile.ogrn,
            "kpp": profile.kpp,
            "address": profile.address,
            "director": profile.director,
            "source_url": profile.source_url,
        }
    if lookups:
        analysis["company_lookup"] = {"source": "rusprofile.ru", "parties": lookups}
    return analysis


def _fill_missing_party_fields(party: dict[str, Any], profile: CompanyProfile) -> None:
    if not str(party.get("name", "")).strip() and profile.name:
        party["name"] = profile.name
    if profile.ogrn and not _valid_ogrn(str(party.get("ogrn", ""))):
        party["ogrn"] = profile.ogrn
    if not str(party.get("address", "")).strip() and profile.address:
        party["address"] = profile.address
    if profile.kpp and not str(party.get("kpp", "")).strip():
        party["kpp"] = profile.kpp
    if profile.director and not str(party.get("representative", "")).strip():
        party["representative"] = profile.director


def _extract_by_id(text: str, element_id: str) -> str:
    match = re.search(
        rf'<span[^>]+id=["\']{re.escape(element_id)}["\'][^>]*>(.*?)</span>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return _clean_html(match.group(1)) if match else ""


def _extract_address(text: str) -> str:
    match = re.search(
        r'<span[^>]+id=["\']clip_address["\'][^>]*>(.*?)</span>\s*</address>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return _clean_html(match.group(1))

    meta = re.search(r"Юридическое лицо зарегистрировано[^.]+по адресу\s+(.+?)\.", _clean_html(text), re.IGNORECASE)
    return meta.group(1).strip() if meta else ""


def _extract_director(text: str) -> str:
    cleaned = _clean_html(text)
    match = re.search(r"(Генеральный директор|Директор)\s+[^-]{0,120}-\s+([А-ЯЁ][А-ЯЁа-яё\s-]+)", cleaned)
    if match:
        return f"{match.group(1)} {match.group(2).strip()}"

    block_match = re.search(
        r'<span class=["\']chief-title["\']>\s*(.*?)\s*</span>.*?<span class=["\']margin-right-s["\']>\s*(.*?)\s*</span>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if block_match:
        title = _clean_html(block_match.group(1))
        name = _clean_html(block_match.group(2))
        return f"{title} {name}".strip()
    return ""


def _extract_name(text: str) -> str:
    match = re.search(r'<meta property=["\']og:title["\'] content=["\'](.*?)["\']', text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return _clean_html(match.group(1))
    title = re.search(r"<title>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    if title:
        return re.split(r"\s+\(", _clean_html(title.group(1)))[0].strip()
    return ""


def _clean_html(value: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", value)
    no_tags = html.unescape(no_tags)
    return re.sub(r"\s+", " ", no_tags).strip()


def _valid_ogrn(value: str) -> bool:
    digits = re.sub(r"\D", "", value or "")
    return len(digits) in {13, 15}
