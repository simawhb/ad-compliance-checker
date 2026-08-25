"""
驷马合规 · 电商页面广告审查系统 — FastAPI 主入口

API 接口：
- POST /api/check          — 原有广告文案审查（保持兼容）
- POST /api/check-page     — 【新增】电商页面 URL 审查
- POST /api/check-page/upload — 【新增】截图上传审查
- POST /api/ocr/preview    — 【新增】OCR 预览（供用户修正）
- GET  /api/result/{id}    — 获取审查结果
- GET  /api/quota          — 免费额度查询
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
import hashlib
import json
from base64 import b64decode
from binascii import Error as Base64Error
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image

from llm import ReviewIncompleteError, review_ecommerce_page, review_ad_copy, ReviewResult
from drafting import (
    generate_draft_candidate,
    merge_required_materials,
    revise_draft_candidate,
)
from rule_catalog import (
    build_rule_context,
    load_rule_catalog,
    rule_ids_in_context,
    select_frontend_rules,
)
from url_safety import validate_public_http_url
from ocr_engine import get_ocr_engine
from page_fetcher import get_page_fetcher
from pdf_report import generate_report
from schemas import (
    CheckPageRequest,
    CheckPageResponse,
    OCRPreviewItem,
    OCRPreviewResponse,
    PlatformEnum,
    RiskLevel,
    ViolationSeverity,
)
from utils.image_utils import ensure_temp_dir, is_image_file

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# FastAPI 应用
# ──────────────────────────────────────────────

app = FastAPI(
    title="驷马合规 · 电商页面广告审查系统",
    version="1.0.0",
    description="支持电商产品页面 URL 自动抓取和截图上传两种模式的广告合规审查",
)

_CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# 内存存储（生产环境应替换为持久化存储）
# ──────────────────────────────────────────────

_review_results: dict[str, "ReviewResult"] = {}
_upload_dir: str = ""
_RULES_DIR_ENV = "AD_COMPLIANCE_RULES_DIR"
_EXPERIMENTAL_MULTIMODAL_ENABLED = (
    os.getenv("ENABLE_EXPERIMENTAL_MULTIMODAL", "false").lower() == "true"
)
_TEXT_REVIEW_SCOPE_NOTICE = (
    "本次仅审查用户提交的广告文字；未审查图片、画面、版式、人物形象、"
    "示意图、视频视觉内容及相关授权事项。"
)
_CONCLUSION_NOTICE = (
    "本结果仅为合规风险提示，不代表广告已经获得合规确认；"
    "未发现明确风险的内容仍需结合主体资质、发布媒介和证明材料复核。"
)
_AI_GENERATION_NOTICE = (
    "本待审文案由人工智能辅助生成，已经过同一规则体系内部审查；"
    "仍须由用户核对事实、资质、证明材料和发布场景后决定是否采用。"
)
_MAX_REVIEW_MATERIAL_CHARS = 20_000
_MAX_BASE64_IMAGE_BYTES = 10 * 1024 * 1024
_MAX_UPLOAD_IMAGE_BYTES = 10 * 1024 * 1024
_MAX_UPLOAD_ARCHIVE_BYTES = 50 * 1024 * 1024
_MAX_UPLOAD_IMAGES = 10
_MAX_UPLOAD_IMAGE_PIXELS = 25_000_000
_RESULT_RETENTION = timedelta(hours=24)
_MAX_STORED_RESULTS = 200
_RESULT_RETENTION_ENABLED = os.getenv("STORE_REVIEW_RESULTS", "false").lower() == "true"
_FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


class AdCopyRequest(BaseModel):
    """与当前网页端 /api/check JSON 请求保持一致。"""

    text: str
    industry: str = ""
    platform: str = ""
    terms_accepted: bool = False


class AdCopyBatchRequest(BaseModel):
    texts: list[str]
    industry: str = ""
    platform: str = ""
    terms_accepted: bool = False


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


class OCRBase64Request(BaseModel):
    image: str


def _store_review_result(result: "ReviewResult") -> None:
    if not _RESULT_RETENTION_ENABLED:
        return
    _prune_review_results()
    if len(_review_results) >= _MAX_STORED_RESULTS:
        oldest_id = min(_review_results, key=lambda item: _review_results[item].created_at)
        _review_results.pop(oldest_id, None)
    _review_results[result.id] = result


def _prune_review_results() -> None:
    cutoff = datetime.now() - _RESULT_RETENTION
    for result_id, stored in list(_review_results.items()):
        if stored.created_at < cutoff:
            _review_results.pop(result_id, None)


def _cleanup_expired_uploads(root: Path | None = None) -> None:
    """仅清理本项目上传临时目录中超过24小时的内容。"""
    upload_root = root or Path(_upload_dir)
    if not upload_root.is_dir():
        return
    cutoff = datetime.now().timestamp() - _RESULT_RETENTION.total_seconds()
    for item in upload_root.iterdir():
        try:
            if item.stat().st_mtime >= cutoff:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except OSError as exc:
            logger.warning("过期上传文件清理失败: %s — %s", item, exc)


app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
async def web_home():
    return FileResponse(_FRONTEND_DIR / "index.html")


@app.get("/h5/", include_in_schema=False)
async def mobile_web_home():
    """手机版入口复用同一响应式页面，避免两套审查逻辑分叉。"""
    return FileResponse(_FRONTEND_DIR / "index.html")


@app.get("/privacy", include_in_schema=False)
async def privacy_page():
    return FileResponse(_FRONTEND_DIR / "privacy.html")


@app.get("/terms", include_in_schema=False)
async def terms_page():
    return FileResponse(_FRONTEND_DIR / "terms.html")


@app.on_event("startup")
async def startup():
    """应用启动初始化"""
    global _upload_dir
    _upload_dir = os.path.join(ensure_temp_dir(), "uploads")
    os.makedirs(_upload_dir, exist_ok=True)
    _cleanup_expired_uploads()
    logger.info("驷马合规 · 电商审查系统启动完成")


# ──────────────────────────────────────────────
# API 路由
# ──────────────────────────────────────────────

@app.post("/api/check")
async def check_ad_copy(request: AdCopyRequest):
    """
    原有广告文案审查（保持兼容）

    Args:
        request: 网页端 JSON 请求

    Returns:
        网页端所需的紧凑审查结果
    """
    if not request.terms_accepted:
        return {"ok": False, "status": "incomplete", "error": "请先确认使用规则和隐私规则"}
    try:
        _ensure_review_material_size(request.text)
        rule_context, rule_ids = _rule_context_for(request.industry, request.platform)
        result = await review_ad_copy(
            request.text, rule_context=rule_context, allowed_rule_ids=rule_ids
        )
        _store_review_result(result)
        return _as_web_review_response(result)
    except ReviewIncompleteError as exc:
        logger.warning("文案审查未完成: %s", exc)
        return {"ok": False, "status": "incomplete", "error": str(exc)}
    except Exception as exc:
        logger.error("文案审查失败: %s", exc)
        return {"ok": False, "status": "failed", "error": "审查服务异常，请稍后重试"}


@app.post("/api/check-batch")
async def check_ad_copy_batch(request: AdCopyBatchRequest):
    if not request.terms_accepted:
        return {"ok": False, "status": "incomplete", "error": "请先确认使用规则和隐私规则"}
    texts = [text.strip() for text in request.texts if text.strip()]
    if not texts:
        return {"ok": False, "status": "incomplete", "error": "批量审查材料不能为空"}
    if len(texts) > 20:
        return {"ok": False, "status": "incomplete", "error": "每批最多提交20条文案"}
    try:
        _ensure_review_material_size(*texts)
    except ReviewIncompleteError as exc:
        return {"ok": False, "status": "incomplete", "error": str(exc)}

    items = [
        await check_ad_copy(AdCopyRequest(
            text=text,
            industry=request.industry,
            platform=request.platform,
            terms_accepted=True,
        ))
        for text in texts
    ]
    return {
        "ok": True,
        "count": len(items),
        "completed": sum(1 for item in items if item.get("ok")),
        "items": items,
    }


@app.post("/api/draft")
async def draft_ad_copy(request: DraftRequest):
    if not request.terms_accepted:
        return {"ok": False, "status": "incomplete", "error": "请先确认使用规则和隐私规则"}
    if request.industry not in {"medical", "ecommerce"}:
        return {
            "ok": False,
            "status": "incomplete",
            "error": "首版起草仅支持医疗健康和电商促销",
        }
    if not all(
        value.strip()
        for value in (
            request.medium,
            request.product_name,
            request.product_type,
            request.verified_facts,
            request.desired_message,
        )
    ):
        return {
            "ok": False,
            "status": "incomplete",
            "error": "请完整填写产品、媒介、已确认事实和表达重点",
        }

    try:
        _ensure_review_material_size(
            request.product_name,
            request.product_type,
            request.verified_facts,
            request.desired_message,
            request.proof_materials,
        )
        rule_context, rule_ids = _rule_context_for(
            request.industry, _draft_platform_code(request.medium)
        )
        industry_name = "医疗健康" if request.industry == "medical" else "电商促销"
        required_materials = _draft_required_materials(
            request.industry, request.details, request.desired_message
        )
        candidate = await generate_draft_candidate(
            industry=industry_name,
            medium=request.medium,
            product_name=request.product_name,
            product_type=request.product_type,
            verified_facts=request.verified_facts,
            desired_message=request.desired_message,
            proof_materials=request.proof_materials,
            structured_facts=_draft_structured_facts(request.industry, request.details),
            required_materials=required_materials,
            rule_context=rule_context,
            allowed_rule_ids=rule_ids,
        )
        candidate = merge_required_materials(
            candidate,
            required_materials,
        )
        review = await review_ad_copy(
            candidate.draft_text,
            rule_context=rule_context,
            allowed_rule_ids=rule_ids,
        )
        repaired = False
        if review.risk_level != RiskLevel.LOW:
            candidate = await revise_draft_candidate(
                candidate,
                review_risks=_review_risks_for_revision(review),
                rule_context=rule_context,
                allowed_rule_ids=rule_ids,
            )
            repaired = True
            review = await review_ad_copy(
                candidate.draft_text,
                rule_context=rule_context,
                allowed_rule_ids=rule_ids,
            )

        review_response = _as_web_review_response(review)
        final_missing_materials = list(
            dict.fromkeys(candidate.missing_materials + review.missing_materials)
        )[:20]
        if review.risk_level != RiskLevel.LOW:
            status = "needs_revision"
            publication_status = "内部审查未通过，仅供继续修改，不得使用"
        elif final_missing_materials:
            status = "pending_materials"
            publication_status = "待补材料的待审版本，不得直接发布"
        else:
            status = "internally_checked"
            publication_status = "已完成内部审查的待审版本，发布前仍需确认"

        input_snapshot = _draft_input_snapshot(request)
        draft_version = _draft_version(candidate.draft_text, rule_context, input_snapshot)
        return {
            "ok": True,
            "status": status,
            "draft_text": candidate.draft_text,
            "draft_version": draft_version,
            "publication_status": publication_status,
            "ai_generation_notice": _AI_GENERATION_NOTICE,
            "missing_materials": final_missing_materials,
            "excluded_claims": candidate.excluded_claims,
            "rule_ids": candidate.rule_ids,
            "input_snapshot": input_snapshot,
            "auto_repaired": repaired,
            "internal_review": review_response,
        }
    except ReviewIncompleteError as exc:
        logger.warning("广告文案起草未完成: %s", exc)
        return {"ok": False, "status": "incomplete", "error": str(exc)}
    except Exception as exc:
        logger.error("广告文案起草失败: %s", exc)
        return {"ok": False, "status": "failed", "error": "起草服务异常，请稍后重试"}


def _draft_platform_code(medium: str) -> str:
    if medium in {"详情页", "落地页", "海报"}:
        return "taobao"
    if medium in {"短视频", "直播口播", "直播"}:
        return "douyin"
    return ""


def _draft_required_materials(
    industry: str, details: dict[str, str], desired_message: str
) -> list[str]:
    missing: list[str] = []
    if industry == "ecommerce":
        required = {
            "sale_price": "实际宣传价格及价格形成依据",
            "promotion_period": "促销活动起止时间",
            "applicable_scope": "活动适用商品、地区和人群范围",
            "promotion_conditions": "优惠门槛、限购、库存及其他适用条件",
        }
        for key, label in required.items():
            if not details.get(key, "").strip():
                missing.append(label)
        if any(word in desired_message for word in ("原价", "折扣", "最低", "降价")):
            if not details.get("reference_price_basis", "").strip():
                missing.append("原价、比较价格或折扣计算依据")
    else:
        category = details.get("regulatory_category", "").strip()
        if not category:
            missing.append("医疗健康产品或服务的监管类别")
        elif category != "general_health_product":
            if not details.get("approval_or_registration", "").strip():
                missing.append("广告审查批准、注册或备案信息")
            if not details.get("approved_ad_text", "").strip():
                missing.append("审查批准样件或获准发布的广告文字")
    return missing


def _draft_structured_facts(industry: str, details: dict[str, str]) -> str:
    labels = {
        "regulatory_category": "监管类别",
        "approval_or_registration": "批准/注册/备案信息",
        "approved_ad_text": "批准或备案文案",
        "sale_price": "宣传价格",
        "promotion_period": "活动期限",
        "applicable_scope": "适用范围",
        "promotion_conditions": "优惠条件",
        "reference_price_basis": "比较价格依据",
    }
    return "\n".join(
        f"{labels[key]}：{value.strip()}"
        for key, value in details.items()
        if key in labels and value.strip()
    )


def _draft_input_snapshot(request: DraftRequest) -> dict:
    return {
        "industry": "医疗健康" if request.industry == "medical" else "电商促销",
        "medium": request.medium,
        "product_name": request.product_name.strip(),
        "product_type": request.product_type.strip(),
        "verified_facts": request.verified_facts.strip(),
        "desired_message": request.desired_message.strip(),
        "proof_materials": request.proof_materials.strip(),
        "structured_facts": _draft_structured_facts(request.industry, request.details),
    }


def _draft_version(draft_text: str, rule_context: str, input_snapshot: dict) -> str:
    payload = json.dumps(
        {
            "draft_text": draft_text,
            "rule_context": rule_context,
            "input_snapshot": input_snapshot,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12].upper()


def _review_risks_for_revision(result: ReviewResult) -> list[dict]:
    return [
        {
            "content": item.content,
            "law_basis": item.law_basis,
            "suggestion": item.suggestion,
            "rule_ids": item.rule_ids,
        }
        for item in result.violation_items[:20]
    ]


def _rule_context_for(industry: str, platform: str) -> tuple[str, set[str]]:
    rules_dir = os.getenv(_RULES_DIR_ENV)
    if not rules_dir:
        raise ReviewIncompleteError("本机规则库未配置，审查未完成")
    rules = select_frontend_rules(load_rule_catalog(rules_dir), industry, platform)
    context = build_rule_context(rules)
    if not context:
        raise ReviewIncompleteError("未找到匹配的已核验规则，审查未完成")
    return context, rule_ids_in_context(context)


def _ensure_review_material_size(*materials: object) -> None:
    normalized = [str(item).strip() for item in materials if item is not None]
    if not any(normalized):
        raise ReviewIncompleteError("审查材料不能为空，审查未完成")
    chars = sum(len(item) for item in normalized)
    if chars > _MAX_REVIEW_MATERIAL_CHARS:
        raise ReviewIncompleteError("审查材料超过 20000 字符，请分批提交，审查未完成")


def _as_web_review_response(result: ReviewResult) -> dict:
    score_by_risk = {
        RiskLevel.HIGH: 25,
        RiskLevel.MEDIUM: 60,
        RiskLevel.LOW: 90,
    }
    risks = [
        {
            "word": item.content,
            "risk_level": _web_risk_level(item.severity),
            "category": item.dimension,
            "law": item.law_basis,
            "suggest": item.suggestion,
            "rule_ids": item.rule_ids,
        }
        for item in result.violation_items
        if item.content != "（无违规）"
    ]
    return {
        "ok": True,
        "score": score_by_risk[result.risk_level],
        "risk_level": result.risk_level.value,
        "summary": result.summary,
        "scope_notice": _TEXT_REVIEW_SCOPE_NOTICE,
        "conclusion_notice": _CONCLUSION_NOTICE,
        "risk_count": len(risks),
        "risks": risks,
        "missing_materials": result.missing_materials,
        "result_id": result.id if _RESULT_RETENTION_ENABLED else "",
        "retained": _RESULT_RETENTION_ENABLED,
    }


def _web_risk_level(severity: ViolationSeverity) -> str:
    if severity == ViolationSeverity.CRITICAL:
        return "high"
    if severity == ViolationSeverity.MEDIUM:
        return "medium"
    return "low"


def _is_safe_image(content: bytes) -> bool:
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            return image.width * image.height <= _MAX_UPLOAD_IMAGE_PIXELS
    except (Image.DecompressionBombError, OSError, ValueError):
        return False


@app.post("/api/ocr-base64")
async def ocr_base64(request: OCRBase64Request):
    """供现有网页端图片上传入口调用的 OCR 接口。"""
    if not _EXPERIMENTAL_MULTIMODAL_ENABLED:
        return {
            "ok": False,
            "status": "unavailable",
            "error": "图片识别属于内部实验功能，当前文字审查版未开放。",
        }
    try:
        encoded = request.image.split(",", 1)[-1]
        content = b64decode(encoded, validate=True)
    except (Base64Error, ValueError):
        return {"ok": False, "error": "图片编码无效"}
    if not content or len(content) > _MAX_BASE64_IMAGE_BYTES:
        return {"ok": False, "error": "图片不能为空或超过 10MB"}
    if not _is_safe_image(content):
        return {"ok": False, "error": "仅支持有效图片文件"}

    session_dir = Path(_upload_dir or ensure_temp_dir() / "uploads") / "ocr-base64"
    session_dir.mkdir(parents=True, exist_ok=True)
    image_path = session_dir / f"{uuid.uuid4().hex}.png"
    image_path.write_bytes(content)
    text = get_ocr_engine().recognize(image_path)
    return {"ok": True, "text": text}


@app.post("/api/deep-check")
async def deep_check(_: AdCopyRequest):
    return {
        "ok": False,
        "status": "unavailable",
        "error": "本机研发暂未启用 AI 深度分析，请使用快速检测。",
    }


@app.post("/api/export-pdf")
async def export_ad_copy_pdf(_: AdCopyRequest):
    return {
        "ok": False,
        "status": "unavailable",
        "error": "本机研发暂未启用文案 PDF 导出。",
    }


@app.post("/api/check-page", response_model=CheckPageResponse)
async def check_page(request: CheckPageRequest):
    """
    电商页面 URL 审查 — 自动抓取 + OCR + Lex 审查

    流程：
    1. 平台识别
    2. Playwright 抓取页面
    3. 提取结构化数据 + 下载详情图
    4. PaddleOCR 识别图片文字
    5. Lex 合规审查
    6. 返回结构化报告

    Args:
        request: CheckPageRequest { url }

    Returns:
        CheckPageResponse
    """
    if not _EXPERIMENTAL_MULTIMODAL_ENABLED:
        return CheckPageResponse(
            success=False,
            error="网页及图片审查属于内部实验功能，当前文字审查版未开放。",
        )

    url = request.url.strip()
    if not url:
        return CheckPageResponse(success=False, error="URL 不能为空")

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        validate_public_http_url(url)
    except ValueError as exc:
        return CheckPageResponse(success=False, error=str(exc))

    try:
        fetcher = get_page_fetcher()
        fetch_result = await fetcher.fetch(url)

        if not fetch_result.success:
            return CheckPageResponse(
                success=False,
                error=fetch_result.error,
                message="如需抓取建议截图上传" if fetch_result.needs_manual else "",
            )

        # 执行 Lex 合规审查
        page_data = fetch_result.page_data
        _ensure_review_material_size(
            page_data.title, page_data.price, page_data.params,
            page_data.description, page_data.ocr_texts,
        )
        result = await review_ecommerce_page(
            title=page_data.title,
            price=page_data.price,
            params=page_data.params,
            description=page_data.description,
            ocr_texts=page_data.ocr_texts,
            platform=page_data.platform,
            url=page_data.url,
        )

        # 生成 PDF
        try:
            pdf_dir = ensure_temp_dir() / "reports"
            pdf_path = pdf_dir / f"{result.id}.pdf"
            generate_report(
                result,
                output_path=pdf_path,
                screenshot_path=page_data.screenshot_path if hasattr(page_data, 'screenshot_path') else None,
            )
            result.page_summary += f" | PDF: {pdf_path}"
        except Exception as exc:
            logger.warning("PDF 生成失败: %s", exc)

        # 存结果
        _store_review_result(result)

        return CheckPageResponse(success=True, result=result)

    except Exception as exc:
        logger.error("URL 审查失败: %s", exc)
        return CheckPageResponse(success=False, error=f"审查异常: {exc}")


@app.post("/api/check-page/upload", response_model=CheckPageResponse)
async def check_page_upload(
    images: list[UploadFile] = File(default=[]),
    text: str = Form(default=""),
):
    """
    截图上传审查（方案 B — 兜底路径）

    适用于淘宝/天猫、拼多多、抖音小店等强反爬平台。

    Args:
        images: 上传的图片文件列表（支持 PNG/JPG/JPEG/ZIP）
        text: 可选的手工粘贴文字

    Returns:
        CheckPageResponse
    """
    if not _EXPERIMENTAL_MULTIMODAL_ENABLED:
        return CheckPageResponse(
            success=False,
            error="图片审查属于内部实验功能，当前文字审查版未开放。",
        )

    if not images and not text:
        return CheckPageResponse(
            success=False,
            error="请至少上传一张截图或输入商品文字描述",
        )

    try:
        # 保存上传文件
        session_id = uuid.uuid4().hex[:8]
        session_dir = os.path.join(_upload_dir, session_id)
        os.makedirs(session_dir, exist_ok=True)

        saved_paths: list[str] = []
        for img in images:
            if len(saved_paths) >= _MAX_UPLOAD_IMAGES:
                break
            if not img.filename:
                continue
            # 检查是否为 ZIP
            if img.filename.lower().endswith(".zip"):
                import zipfile
                zip_path = os.path.join(session_dir, img.filename)
                content = await img.read()
                if len(content) > _MAX_UPLOAD_ARCHIVE_BYTES:
                    return CheckPageResponse(success=False, error="ZIP 文件超过 50MB 限制")
                with open(zip_path, "wb") as f:
                    f.write(content)
                # 解压
                try:
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        for info in zf.infolist():
                            if info.is_dir() or len(saved_paths) >= _MAX_UPLOAD_IMAGES:
                                continue
                            if not is_image_file(info.filename):
                                continue
                            if info.file_size > _MAX_UPLOAD_IMAGE_BYTES:
                                continue
                            filename = Path(info.filename).name
                            if not filename:
                                continue
                            image_content = zf.read(info)
                            if not _is_safe_image(image_content):
                                continue
                            dest = os.path.join(session_dir, f"{uuid.uuid4().hex}_{filename}")
                            with open(dest, "wb") as dst:
                                dst.write(image_content)
                            saved_paths.append(dest)
                except Exception as exc:
                    logger.warning("ZIP 解压失败: %s", exc)
            elif is_image_file(img.filename):
                content = await img.read()
                if len(content) > _MAX_UPLOAD_IMAGE_BYTES or not _is_safe_image(content):
                    continue
                filename = Path(img.filename).name
                if not filename:
                    continue
                dest = os.path.join(session_dir, f"{uuid.uuid4().hex}_{filename}")
                with open(dest, "wb") as f:
                    f.write(content)
                saved_paths.append(dest)

        if not saved_paths:
            return CheckPageResponse(
                success=False,
                error="未找到有效的图片文件（支持 PNG/JPG/JPEG，或 ZIP 压缩包）",
            )

        # 方案B处理
        fetcher = get_page_fetcher()
        fetch_result = await fetcher.fetch_with_upload(
            image_paths=saved_paths,
            text=text,
        )

        if not fetch_result.success:
            return CheckPageResponse(success=False, error=fetch_result.error)

        # Lex 审查
        page_data = fetch_result.page_data
        _ensure_review_material_size(page_data.description, page_data.ocr_texts)
        result = await review_ecommerce_page(
            title="",
            price="",
            params="",
            description=page_data.description,
            ocr_texts=page_data.ocr_texts,
            platform=PlatformEnum.MANUAL,
            url="",
        )

        # 生成 PDF
        try:
            pdf_dir = ensure_temp_dir() / "reports"
            pdf_path = pdf_dir / f"{result.id}.pdf"
            generate_report(result, output_path=pdf_path)
        except Exception as exc:
            logger.warning("PDF 生成失败: %s", exc)

        _store_review_result(result)

        return CheckPageResponse(success=True, result=result)

    except Exception as exc:
        logger.error("上传审查失败: %s", exc)
        return CheckPageResponse(success=False, error=f"处理异常: {exc}")


@app.post("/api/ocr/preview", response_model=OCRPreviewResponse)
async def ocr_preview(
    images: list[UploadFile] = File(default=[]),
):
    """
    OCR 预览 — 用户上传图片后先显示识别结果，可手动修正

    Args:
        images: 待识别的图片文件

    Returns:
        OCRPreviewResponse { items: [{ image_index, image_filename, recognized_text }], merged_text }
    """
    if not _EXPERIMENTAL_MULTIMODAL_ENABLED:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "status": "unavailable",
                "error": "图片识别属于内部实验功能，当前文字审查版未开放。",
            },
        )

    if not images:
        return OCRPreviewResponse(success=False, items=[], merged_text="")

    ocr = get_ocr_engine()
    items: list[OCRPreviewItem] = []
    all_texts: list[str] = []

    session_dir = os.path.join(_upload_dir, f"preview_{uuid.uuid4().hex[:8]}")
    os.makedirs(session_dir, exist_ok=True)

    for i, img in enumerate(images):
        if not img.filename or not is_image_file(img.filename):
            continue
        content = await img.read()
        if len(content) > _MAX_UPLOAD_IMAGE_BYTES or not _is_safe_image(content):
            continue
        filename = Path(img.filename).name
        if not filename:
            continue
        dest = os.path.join(session_dir, f"{uuid.uuid4().hex}_{filename}")
        with open(dest, "wb") as f:
            f.write(content)

        text = ocr.recognize(dest)
        items.append(OCRPreviewItem(
            image_index=i,
            image_filename=img.filename,
            recognized_text=text,
        ))
        all_texts.append(text)

    return OCRPreviewResponse(
        success=True,
        items=items,
        merged_text="\n".join(all_texts),
    )


@app.get("/api/result/{result_id}")
async def get_result(result_id: str):
    """获取审查结果详情"""
    if not _RESULT_RETENTION_ENABLED:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "当前未启用审查结果留存"},
        )
    _prune_review_results()
    result = _review_results.get(result_id)
    if not result:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "审查结果不存在"},
        )
    return JSONResponse(content=result.model_dump())


@app.get("/api/result/{result_id}/pdf")
async def get_result_pdf(result_id: str):
    """下载审查结果 PDF"""
    if not _RESULT_RETENTION_ENABLED:
        raise HTTPException(status_code=404, detail="当前未启用审查结果留存")
    result = _review_results.get(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="审查结果不存在")

    pdf_dir = ensure_temp_dir() / "reports"
    pdf_path = pdf_dir / f"{result.id}.pdf"

    if not pdf_path.exists():
        # 重新生成
        generate_report(result, output_path=pdf_path)

    if pdf_path.exists():
        return FileResponse(
            str(pdf_path),
            media_type="application/pdf",
            filename=f"驷马合规报告_{result_id}.pdf",
        )

    raise HTTPException(status_code=500, detail="PDF 文件生成失败")


@app.get("/api/quota")
async def get_quota():
    """额度体系尚未接入时不得返回虚构数值。"""
    return JSONResponse(
        status_code=503,
        content={
            "success": False,
            "status": "unavailable",
            "error": "本机研发暂未接入账号与额度体系。",
        },
    )


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/readiness")
async def readiness():
    """审查能力就绪检查；不发起模型调用。"""
    rules_dir = os.getenv(_RULES_DIR_ENV, "")
    components = {
        "rules": Path(rules_dir).is_dir(),
        "model": bool(os.getenv("DEEPSEEK_API_KEY")),
    }
    ready = all(components.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "components": components,
            "capabilities": {
                "text_review": ready,
                "image_ocr": _EXPERIMENTAL_MULTIMODAL_ENABLED,
                "visual_review": False,
                "result_retention": _RESULT_RETENTION_ENABLED,
            },
            "timestamp": datetime.now().isoformat(),
        },
    )
