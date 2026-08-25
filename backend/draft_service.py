"""纯文字广告合规起草服务：独立部署，不导入 OCR 或网页抓取模块。"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from drafting import generate_draft_candidate, merge_required_materials, revise_draft_candidate
from llm import ReviewIncompleteError, review_ad_copy
from rule_catalog import build_rule_context, load_rule_catalog, rule_ids_in_context, select_frontend_rules
from schemas import RiskLevel, ViolationSeverity

logger = logging.getLogger(__name__)
RULES_DIR_ENV = "AD_COMPLIANCE_RULES_DIR"
MAX_MATERIAL_CHARS = 20_000
SCOPE_NOTICE = "本次仅审查用户提交的广告文字，不审查图片、视频、资质文件或发布画面。"
CONCLUSION_NOTICE = "本结果仅为合规风险提示，不代表广告已经获得合规确认。"
AI_NOTICE = "人工智能辅助生成；采用前仍须核对事实、资质、证明材料和发布场景。"
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"

app = FastAPI(title="驷马合规·广告宣传合规起草助手", version="1.0.0")
origins = [item.strip() for item in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["POST", "GET"], allow_headers=["Content-Type"])


@app.middleware("http")
async def prevent_draft_caching(request: Request, call_next):
    response = await call_next(request)
    if request.url.path in {"/", "/api/draft"}:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


class DraftRequest(BaseModel):
    industry: str
    medium: str
    product_name: str
    product_type: str
    verified_facts: str
    desired_message: str
    proof_materials: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    terms_accepted: bool = False


@app.get("/", include_in_schema=False)
async def draft_home() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "draft.html")


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {"ok": True, "service": "text-draft"}


@app.post("/api/draft")
async def draft_ad_copy(request: DraftRequest) -> dict[str, object]:
    if not request.terms_accepted:
        return incomplete("请先确认使用规则和隐私规则")
    if request.industry not in {"medical", "ecommerce"}:
        return incomplete("首版起草仅支持医疗健康和电商促销")
    if not all(value.strip() for value in (request.medium, request.product_name, request.product_type, request.verified_facts, request.desired_message)):
        return incomplete("请完整填写产品、媒介、已确认事实和表达重点")
    try:
        ensure_material_size(request.product_name, request.product_type, request.verified_facts, request.desired_message, request.proof_materials)
        context, rule_ids = rule_context_for(request.industry, platform_code(request.medium))
        required = required_materials(request.industry, request.details, request.desired_message, product_type=request.product_type, medium=request.medium)
        for attempt in range(2):
            try:
                candidate = await generate_draft_candidate(
                    industry="医疗健康" if request.industry == "medical" else "电商促销",
                    medium=request.medium,
                    product_name=request.product_name,
                    product_type=request.product_type,
                    verified_facts=request.verified_facts,
                    desired_message=request.desired_message,
                    proof_materials=request.proof_materials,
                    structured_facts=structured_facts(request.details),
                    required_materials=required,
                    rule_context=context,
                    allowed_rule_ids=rule_ids,
                )
                break
            except ReviewIncompleteError as exc:
                if attempt or str(exc) != "起草模型未返回待审文案":
                    raise
        candidate = merge_required_materials(candidate, required)
        review = await review_ad_copy(candidate.draft_text, rule_context=context, allowed_rule_ids=rule_ids)
        repaired = False
        if review.risk_level != RiskLevel.LOW:
            candidate = await revise_draft_candidate(candidate, review_risks=revision_risks(review), rule_context=context, allowed_rule_ids=rule_ids)
            repaired = True
            review = await review_ad_copy(candidate.draft_text, rule_context=context, allowed_rule_ids=rule_ids)
        missing = list(dict.fromkeys(candidate.missing_materials + review.missing_materials))[:20]
        if review.risk_level != RiskLevel.LOW:
            status, publication = "needs_revision", "内部审查未通过，仅供继续修改，不得使用"
        elif missing:
            status, publication = "pending_materials", "待补材料的待审版本，不得直接发布"
        else:
            status, publication = "internally_checked", "已完成内部审查的待审版本，发布前仍需确认"
        snapshot = input_snapshot(request)
        return {
            "ok": True, "status": status, "draft_text": candidate.draft_text,
            "draft_version": draft_version(candidate.draft_text, context, snapshot),
            "publication_status": publication, "ai_generation_notice": AI_NOTICE,
            "missing_materials": missing, "excluded_claims": candidate.excluded_claims,
            "rule_ids": candidate.rule_ids, "input_snapshot": snapshot,
            "auto_repaired": repaired, "internal_review": web_review(review),
        }
    except ReviewIncompleteError as exc:
        return incomplete(str(exc))
    except Exception:
        logger.exception("广告文案起草失败")
        return {"ok": False, "status": "failed", "error": "起草服务异常，请稍后重试"}


def incomplete(message: str) -> dict[str, object]:
    return {"ok": False, "status": "incomplete", "error": message}


def platform_code(medium: str) -> str:
    return "taobao" if medium in {"详情页", "落地页", "海报"} else "douyin" if medium in {"短视频", "直播口播", "直播"} else ""


def required_materials(industry: str, details: dict[str, str], desired_message: str, *, product_type: str = "", medium: str = "") -> list[str]:
    if industry == "ecommerce":
        fields = {"sale_price": "实际宣传价格及价格形成依据", "promotion_period": "促销活动起止时间", "applicable_scope": "活动适用商品、地区和人群范围", "promotion_conditions": "优惠门槛、限购、库存及其他适用条件"}
        missing = [label for key, label in fields.items() if not details.get(key, "").strip()]
        if any(word in desired_message for word in ("原价", "折扣", "最低", "降价")) and not details.get("reference_price_basis", "").strip():
            missing.append("原价、比较价格或折扣计算依据")
        if "化妆品" in product_type and any(word in desired_message for word in ("医用", "抗炎", "治疗", "祛斑", "生发", "处方", "药妆")) and not details.get("cosmetic_compliance_materials", "").strip():
            missing.append("化妆品备案或注册信息及对应功效宣称依据摘要")
        if medium in {"直播口播", "直播"} and any(word in desired_message for word in ("保证", "最低", "退款", "功效", "治愈")):
            if not details.get("live_roles", "").strip():
                missing.append("商品销售者、直播间运营者和主播角色说明")
            if not details.get("live_assets", "").strip():
                missing.append("直播话术、字幕和商品卡版本")
        return missing
    category = details.get("regulatory_category", "").strip()
    if not category:
        return ["医疗健康产品或服务的监管类别"]
    if category == "general_health_product":
        return []
    return [label for key, label in {"approval_or_registration": "广告审查批准、注册或备案信息", "approved_ad_text": "审查批准样件或获准发布的广告文字"}.items() if not details.get(key, "").strip()]


def structured_facts(details: dict[str, str]) -> str:
    labels = {"regulatory_category": "监管类别", "approval_or_registration": "批准/注册/备案信息", "approved_ad_text": "批准或备案文案", "sale_price": "宣传价格", "promotion_period": "活动期限", "applicable_scope": "适用范围", "promotion_conditions": "优惠条件", "reference_price_basis": "比较价格依据", "cosmetic_compliance_materials": "化妆品备案/功效依据", "live_roles": "直播角色", "live_assets": "直播素材版本"}
    return "\n".join(f"{labels[key]}：{value.strip()}" for key, value in details.items() if key in labels and value.strip())


def input_snapshot(request: DraftRequest) -> dict[str, str]:
    return {"industry": "医疗健康" if request.industry == "medical" else "电商促销", "medium": request.medium, "product_name": request.product_name.strip(), "product_type": request.product_type.strip(), "verified_facts": request.verified_facts.strip(), "desired_message": request.desired_message.strip(), "proof_materials": request.proof_materials.strip(), "structured_facts": structured_facts(request.details)}


def ensure_material_size(*materials: object) -> None:
    values = [str(item).strip() for item in materials if item is not None]
    if not any(values):
        raise ReviewIncompleteError("审查材料不能为空，审查未完成")
    if sum(len(item) for item in values) > MAX_MATERIAL_CHARS:
        raise ReviewIncompleteError("审查材料超过 20000 字符，请分批提交，审查未完成")


def rule_context_for(industry: str, platform: str) -> tuple[str, set[str]]:
    rules_dir = os.getenv(RULES_DIR_ENV)
    if not rules_dir:
        raise ReviewIncompleteError("本机规则库未配置，审查未完成")
    context = build_rule_context(select_frontend_rules(load_rule_catalog(rules_dir), industry, platform))
    if not context:
        raise ReviewIncompleteError("未找到匹配的已核验规则，审查未完成")
    return context, rule_ids_in_context(context)


def revision_risks(result) -> list[dict[str, object]]:
    return [{"content": item.content, "law_basis": item.law_basis, "suggestion": item.suggestion, "rule_ids": item.rule_ids} for item in result.violation_items[:20]]


def draft_version(draft_text: str, context: str, snapshot: dict[str, str]) -> str:
    payload = json.dumps({"draft_text": draft_text, "rule_context": context, "input_snapshot": snapshot}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12].upper()


def web_review(result) -> dict[str, object]:
    score = {RiskLevel.HIGH: 25, RiskLevel.MEDIUM: 60, RiskLevel.LOW: 90}[result.risk_level]
    risks = [{"word": item.content, "risk_level": "high" if item.severity == ViolationSeverity.CRITICAL else "medium" if item.severity == ViolationSeverity.MEDIUM else "low", "category": item.dimension, "law": item.law_basis, "suggest": item.suggestion, "rule_ids": item.rule_ids} for item in result.violation_items if item.content != "（无违规）"]
    return {"ok": True, "score": score, "risk_level": result.risk_level.value, "summary": result.summary, "scope_notice": SCOPE_NOTICE, "conclusion_notice": CONCLUSION_NOTICE, "risk_count": len(risks), "risks": risks, "missing_materials": result.missing_materials, "result_id": "", "retained": False}
