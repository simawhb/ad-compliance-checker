"""
LLM 调用封装 — 电商广告合规审查引擎

支持两种审查模式：
- ad:     原广告文案审查
- ecommerce: 电商页面多维度深度审查（新增）
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

from schemas import (
    PlatformEnum,
    ReviewResult,
    RiskLevel,
    ViolationItem,
    ViolationSeverity,
)

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class ReviewIncompleteError(RuntimeError):
    """模型审查未完成；调用方不得将其显示为低风险。"""


# DeepSeek V4 Pro 配置
DEEPSEEK_API_URL = os.getenv(
    "DEEPSEEK_API_URL",
    "https://api.deepseek.com/v1/chat/completions",  # 请替换为实际端点
)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

# 超时配置
LLM_TIMEOUT = 60  # 秒


# ═══════════════════════════════════════════════════
# 审查 Prompt 模板
# ═══════════════════════════════════════════════════

ECOMMERCE_REVIEW_PROMPT = """你是一名专业的广告合规审查官（Lex），现收到一份电商产品页面的完整内容，请对标以下法律法规进行多维度深度审查：
- 《中华人民共和国广告法》
- 《中华人民共和国反不正当竞争法》
- 《中华人民共和国消费者权益保护法》
- 《中华人民共和国电子商务法》
- 市场监管总局《互联网广告管理办法》
- 市场监管执法检查口径

## 商品信息
【标题】{title}
【价格】{price}
【商品参数】{params}
【描述文字】{description}
【详情图OCR识别文字】{ocr_texts}

## 已核验规则摘要
{rule_context}
仅以以上规则摘要和已列法规作为审查依据；材料不足时明确说明待补材料，不得虚构规则或事实。
仅审查用户提交的文字，不得推断未提供的图片、画面、版式、人物形象、示意图、视频视觉内容或授权事实。

## 审查要求
请从以下 7 个维度逐项审查，每个维度标注违规点（如无违规则写"无违规"）：

1. **标题审查**：是否含有绝对化用语（最好/第一/极致/唯一等）、虚假宣称、违禁词
2. **价格审查**：原价/现价比对是否合理、划线价是否有依据、是否存在虚假优惠
3. **功效宣称**：是否含有医疗用语（治疗/治愈/抗炎）、保健功效宣称、食品功效宣称
4. **数据来源**：销量数据、好评率、排行榜等是否有出处、是否真实可信
5. **资质展示**：荣誉证书、检测报告、专利等是否真实、是否在有效期内
6. **对比广告**：与竞品对比是否客观、是否贬低对手
7. **极限词审查**：是否使用国家级/最高级/最佳等极限词汇

## 输出格式（必须严格按以下 JSON 格式输出，不要添加额外内容）
{{
    "summary": "审查结论概述（1-2句话）",
    "risk_level": "高风险|中风险|低风险",
    "missing_materials": ["仍需补充核验的证明、资质或数据来源；没有则为空数组"],
    "violations": [
        {{
            "dimension": "审查维度",
            "content": "违规原文",
            "severity": "严重|中等|轻微",
            "law_basis": "违反的法条",
            "suggestion": "修改建议",
            "rule_ids": ["关联的已核验规则编号；无匹配则为空数组"],
            "penalty_reference": "典型处罚案例参考"
        }}
    ]
}}"""


# ═══════════════════════════════════════════════════
# LLM 客户端
# ═══════════════════════════════════════════════════

class LLMClient:
    """LLM API 客户端"""

    def __init__(
        self,
        api_key: str = "",
        api_url: str = "",
        model: str = DEEPSEEK_MODEL,
    ):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.api_url = api_url or DEEPSEEK_API_URL
        self.model = model

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: Optional[dict] = None,
    ) -> str:
        """
        调用 LLM API

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数（审查任务用低温度）
            max_tokens: 最大输出 token

        Returns:
            LLM 返回的文本内容
        """
        if not self.api_key:
            raise ReviewIncompleteError("未配置审查模型，无法完成合规分析")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
                resp = await client.post(self.api_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                logger.info("LLM 调用成功 (%d tokens)", data.get("usage", {}).get("total_tokens", 0))
                return content
        except httpx.TimeoutException:
            logger.error("LLM 请求超时 (%ds)", LLM_TIMEOUT)
            raise
        except Exception as exc:
            # Provider error text can include remote response fragments. Do not log it.
            logger.error("LLM 调用失败: %s", type(exc).__name__)
            raise

    # ══════════════════════════════════════════════
    # 模拟审查（无 API KEY 时的兜底）
    # ══════════════════════════════════════════════

    def _mock_review(self, messages: list[dict]) -> str:
        """模拟审查结果（开发测试用）"""
        import uuid
        last_msg = messages[-1]["content"] if messages else ""

        # 简单关键词检测
        violations: list[dict] = []
        risk = "低风险"

        extreme_words = ["最好", "第一", "极致", "唯一", "国家级", "最高级", "最佳"]
        medical_words = ["治疗", "治愈", "抗炎", "疗效", "药用"]

        for word in extreme_words:
            if word in last_msg:
                violations.append({
                    "dimension": "极限词审查",
                    "content": f"使用了绝对化用语「{word}」",
                    "severity": "中等",
                    "law_basis": "违反《广告法》第九条第（三）项：广告不得使用「国家级」「最高级」「最佳」等用语",
                    "suggestion": f"删除「{word}」或替换为具体可验证的描述",
                    "penalty_reference": "市场监管总局典型案例：某品牌使用「最好」被处罚款20万元",
                })
                risk = "中风险"

        for word in medical_words:
            if word in last_msg:
                violations.append({
                    "dimension": "功效宣称",
                    "content": f"使用了医疗用语「{word}」",
                    "severity": "严重",
                    "law_basis": "违反《广告法》第十七条：除医疗、药品、医疗器械广告外，禁止其他广告涉及疾病治疗功能",
                    "suggestion": f"删除「{word}」相关表述，改用具体产品特性描述",
                    "penalty_reference": "上海市监局案例：普通食品宣称「抗炎」被罚50万元",
                })
                risk = "高风险"

        if not violations:
            violations.append({
                "dimension": "标题审查",
                "content": "（无违规）",
                "severity": "轻微",
                "law_basis": "",
                "suggestion": "无需修改",
                "penalty_reference": "",
            })

        result = {
            "summary": f"模拟审查完成，发现 {len([v for v in violations if v['severity'] != '轻微'])} 处违规",
            "risk_level": risk,
            "violations": violations,
        }
        return json.dumps(result, ensure_ascii=False)


# ═══════════════════════════════════════════════════
# 审查函数
# ═══════════════════════════════════════════════════

# 全局 LLM 客户端
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取全局 LLM 客户端"""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


async def review_ecommerce_page(
    title: str = "",
    price: str = "",
    params: dict | str = "",
    description: str = "",
    ocr_texts: list[str] | None = None,
    platform: PlatformEnum = PlatformEnum.UNKNOWN,
    url: str = "",
    rule_context: str = "（未提供规则摘要）",
    allowed_rule_ids: set[str] | None = None,
) -> ReviewResult:
    """
    执行电商页面合规审查（Lex 审核）

    Args:
        title: 商品标题
        price: 价格标签
        params: 商品参数字典或字符串
        description: 商品描述文字
        ocr_texts: 详情图 OCR 识别文本
        platform: 电商平台
        url: 页面 URL

    Returns:
        ReviewResult 结构化审查结果
    """
    llm = get_llm_client()

    # 格式化参数
    if isinstance(params, str):
        params_str = params
    else:
        params_str = "\n".join(f"{k}: {v}" for k, v in params.items())

    ocr_str = "\n---\n".join(ocr_texts) if ocr_texts else "（无详情图OCR内容）"

    # 构建 Prompt
    prompt = ECOMMERCE_REVIEW_PROMPT.format(
        title=title or "（未获取到标题）",
        price=price or "（未获取到价格）",
        params=params_str or "（未获取到参数）",
        description=description or "（未获取到描述）",
        ocr_texts=ocr_str,
        rule_context=rule_context,
    )

    messages = [
        {
            "role": "system",
            "content": "你是一名专业的广告合规审查官Lex。严格遵循输出格式，只输出JSON。",
        },
        {"role": "user", "content": prompt},
    ]

    try:
        content = await llm.chat(messages)

        # 解析 JSON 结果
        result_data = _parse_llm_response(content)

        # 构造 ReviewResult
        violations = []
        for v in result_data.get("violations", []):
            severity = ViolationSeverity.CRITICAL
            if v.get("severity") == "中等":
                severity = ViolationSeverity.MEDIUM
            elif v.get("severity") == "轻微":
                severity = ViolationSeverity.MINOR

            # 跳过明显无违规项
            if v.get("content", "").strip() in ("（无违规）", "无违规", ""):
                continue

            violations.append(
                ViolationItem(
                    dimension=v.get("dimension", "未知"),
                    content=v.get("content", ""),
                    severity=severity,
                    law_basis=v.get("law_basis", ""),
                    suggestion=_safe_suggestion(
                        v.get("content", ""),
                        v.get("suggestion", ""),
                    ),
                    rule_ids=_verified_rule_ids(v.get("rule_ids"), allowed_rule_ids),
                    penalty_reference=v.get("penalty_reference", ""),
                )
            )

        risk = RiskLevel.LOW
        if result_data.get("risk_level", "").startswith("高"):
            risk = RiskLevel.HIGH
        elif result_data.get("risk_level", "").startswith("中"):
            risk = RiskLevel.MEDIUM

        import uuid
        review_id = f"EC-{int(time.time())}-{uuid.uuid4().hex[:6]}"

        return ReviewResult(
            id=review_id,
            channel="url" if url else "upload",
            platform=platform,
            url=url,
            page_summary=f"标题: {title[:50] if title else 'N/A'} | 平台: {platform.value}",
            violation_items=violations,
            missing_materials=_normalized_missing_materials(
                result_data.get("missing_materials")
            ),
            risk_level=risk,
            summary=result_data.get("summary", "审查完成"),
        )

    except ReviewIncompleteError:
        raise
    except Exception as exc:
        logger.error("电商审查失败: %s", type(exc).__name__)
        raise ReviewIncompleteError("审查未完成，请稍后重试。") from exc


async def review_ad_copy(
    text: str,
    rule_context: str = "（未提供规则摘要）",
    allowed_rule_ids: set[str] | None = None,
) -> ReviewResult:
    """
    原有广告文案审查（保持兼容）

    Args:
        text: 广告文案

    Returns:
        ReviewResult
    """
    # 复用电商审查 prompt 但只有文字内容
    return await review_ecommerce_page(
        description=text,
        platform=PlatformEnum.MANUAL,
        rule_context=rule_context,
        allowed_rule_ids=allowed_rule_ids,
    )


def _verified_rule_ids(raw_rule_ids: object, allowed_rule_ids: set[str] | None) -> list[str]:
    if not isinstance(raw_rule_ids, list):
        return []
    rule_ids = [str(rule_id) for rule_id in raw_rule_ids]
    if allowed_rule_ids is None:
        return rule_ids
    return [rule_id for rule_id in rule_ids if rule_id in allowed_rule_ids]


def _normalized_missing_materials(raw_materials: object) -> list[str]:
    """只接受简短字符串列表，避免模型异常结构污染报告。"""
    if not isinstance(raw_materials, list):
        return []
    materials: list[str] = []
    for item in raw_materials[:10]:
        if not isinstance(item, str):
            continue
        normalized = " ".join(item.split()).strip()
        if normalized and normalized not in materials:
            materials.append(normalized[:200])
    return materials


def _safe_suggestion(content: object, suggestion: object) -> str:
    """阻止模型用另一项未经证明的宣传主张替换已识别风险。"""
    risk_text = f"{content} {suggestion}"
    medical_claims = (
        "治疗", "治愈", "疗效", "抗炎", "药用", "改善", "缓解",
        "预防", "康复", "有效率",
    )
    comparative_claims = (
        "国家级", "最高级", "最佳", "最好", "第一", "唯一",
        "全网最低", "最低价", "原价", "销量第一",
    )
    if any(term in risk_text for term in medical_claims):
        return (
            "删除相关疾病治疗或功效表述；仅在法定允许且已有相应资质、"
            "批准内容和证明材料时，依据获准内容另行起草。"
        )
    if any(term in risk_text for term in comparative_claims):
        return (
            "删除该绝对化、排名或价格比较表述；如确需表达，"
            "先补充比较范围、数据来源、有效期或价格依据，再依据已确认事实起草。"
        )
    normalized = " ".join(str(suggestion or "").split()).strip()
    return normalized[:500] or "删除或改写该表述，并在补齐可核验依据后再次审查。"


# ═══════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════

def _parse_llm_response(content: str) -> dict:
    """解析 LLM 返回的 JSON"""
    # 尝试直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 尝试提取 JSON 块（```json ... ```）
    import re
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试从花括号提取
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.error("无法解析 LLM 返回")
    raise ReviewIncompleteError("模型返回无法解析，审查未完成")
