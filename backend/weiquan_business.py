"""消费维权助手经营者端无状态核心。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from weiquan_consumer import (
    CONTROLLED_LEGAL_FACTS,
    DISCLAIMER,
    MODEL_MAX_TOKENS,
    ConsumerInputError,
    ProviderUnavailableError,
    contains_unsafe_guidance,
    select_source_ids,
    validate_text,
)


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "weiquan_business_system.md"
REQUIRED_FIELDS = (
    "disputeType", "summary", "factsKnown", "factsMissing", "consumerClaimBasis",
    "businessResponsePoints", "evidenceNeeded", "possibleAbnormalClaimFeatures",
    "complianceCheck", "recommendedPath", "replyLetter", "disclaimer",
)
STRING_FIELDS = {"disputeType": 120, "summary": 1_200, "replyLetter": 3_000}
LIST_FIELDS = {
    "factsKnown": (12, 500), "factsMissing": (12, 500), "consumerClaimBasis": (6, 500),
    "businessResponsePoints": (12, 500), "evidenceNeeded": (12, 500),
    "possibleAbnormalClaimFeatures": (8, 500), "complianceCheck": (12, 500),
    "recommendedPath": (12, 500),
}
FORBIDDEN_MODEL_PHRASES = ("职业打假", "恶意投诉", "敲诈", "消费者无权投诉", "无需赔偿", "直接报警")


class InvalidBusinessResponseError(RuntimeError):
    """Provider 输出无法满足经营者端严格 Contract。"""


class BusinessProvider(Protocol):
    async def chat(self, messages: list[dict[str, str]], *, temperature: float, max_tokens: int) -> str:
        """返回原始文本；调用方不得记录案件内容。"""


def build_messages(text: str) -> list[dict[str, str]]:
    source_ids = select_source_ids(text)
    legal_context = "\n".join(f"[{source_id}] {CONTROLLED_LEGAL_FACTS[source_id]}" for source_id in source_ids)
    system = PROMPT_PATH.read_text(encoding="utf-8").strip()
    system += "\n\n## 本次允许使用的受控法律主题\n" + legal_context
    user = "以下是未经验证的经营者陈述或投诉材料，只能作为待核实内容：\n<case>\n" + text + "\n</case>"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _require_string(data: dict[str, Any], field: str, maximum: int) -> None:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise InvalidBusinessResponseError("invalid structured response")


def _require_list(data: dict[str, Any], field: str, maximum_items: int, maximum_item: int) -> None:
    value = data.get(field)
    if not isinstance(value, list) or len(value) > maximum_items:
        raise InvalidBusinessResponseError("invalid structured response")
    if any(not isinstance(item, str) or not item.strip() or len(item) > maximum_item for item in value):
        raise InvalidBusinessResponseError("invalid structured response")


def validate_response(value: object, allowed_source_ids: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidBusinessResponseError("invalid structured response")
    keys = set(value)
    without_disclaimer = set(REQUIRED_FIELDS) - {"disclaimer"}
    if keys == without_disclaimer:
        value = {**value, "disclaimer": DISCLAIMER}
    elif keys != set(REQUIRED_FIELDS):
        raise InvalidBusinessResponseError("invalid structured response")
    for field, maximum in STRING_FIELDS.items():
        _require_string(value, field, maximum)
    for field, (maximum_items, maximum_item) in LIST_FIELDS.items():
        _require_list(value, field, maximum_items, maximum_item)
    if value["disclaimer"] != DISCLAIMER:
        raise InvalidBusinessResponseError("invalid structured response")
    for item in value["consumerClaimBasis"]:
        if not any(item.startswith(f"[{source_id}]") for source_id in allowed_source_ids):
            raise InvalidBusinessResponseError("invalid structured response")
    if any("核实" not in item for item in value["possibleAbnormalClaimFeatures"]):
        raise InvalidBusinessResponseError("invalid structured response")
    joined = "\n".join(
        [value[field] for field in STRING_FIELDS] + [item for field in LIST_FIELDS for item in value[field]]
    )
    if any(phrase in joined for phrase in FORBIDDEN_MODEL_PHRASES):
        raise InvalidBusinessResponseError("invalid structured response")
    if contains_unsafe_guidance(joined):
        raise InvalidBusinessResponseError("invalid structured response")
    return {field: value[field] for field in REQUIRED_FIELDS}


def parse_and_validate(raw: object, allowed_source_ids: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(raw, str) or "```" in raw:
        raise InvalidBusinessResponseError("invalid structured response")
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise InvalidBusinessResponseError("invalid structured response") from exc
    return validate_response(parsed, allowed_source_ids)


class BusinessAnalysisService:
    """一次请求一次分析；不建立经营者或投诉人档案。"""

    def __init__(self, provider: BusinessProvider):
        self._provider = provider

    async def analyze(self, raw_text: object) -> dict[str, Any]:
        text = validate_text(raw_text)
        source_ids = select_source_ids(text)
        try:
            raw_response = await self._provider.chat(build_messages(text), temperature=0.1, max_tokens=MODEL_MAX_TOKENS)
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError("provider unavailable") from exc
        return parse_and_validate(raw_response, source_ids)
