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
import uuid
from datetime import datetime

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from llm import review_ecommerce_page, review_ad_copy, ReviewResult
from ocr_engine import get_ocr_engine
from page_fetcher import get_page_fetcher
from pdf_report import generate_report
from schemas import (
    CheckPageRequest,
    CheckPageResponse,
    OCRPreviewItem,
    OCRPreviewResponse,
    PlatformEnum,
    QuotaInfo,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# 内存存储（生产环境应替换为持久化存储）
# ──────────────────────────────────────────────

_review_results: dict[str, "ReviewResult"] = {}
_upload_dir: str = ""


@app.on_event("startup")
async def startup():
    """应用启动初始化"""
    global _upload_dir
    _upload_dir = os.path.join(ensure_temp_dir(), "uploads")
    os.makedirs(_upload_dir, exist_ok=True)
    logger.info("驷马合规 · 电商审查系统启动完成")


# ──────────────────────────────────────────────
# API 路由
# ──────────────────────────────────────────────

@app.post("/api/check")
async def check_ad_copy(text: str = Form(...)):
    """
    原有广告文案审查（保持兼容）

    Args:
        text: 广告文案内容

    Returns:
        CheckPageResponse
    """
    try:
        result = await review_ad_copy(text)
        _review_results[result.id] = result
        return CheckPageResponse(success=True, result=result)
    except Exception as exc:
        logger.error("文案审查失败: %s", exc)
        return CheckPageResponse(success=False, error=str(exc))


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
    url = request.url.strip()
    if not url:
        return CheckPageResponse(success=False, error="URL 不能为空")

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

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
        _review_results[result.id] = result

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
            if not img.filename:
                continue
            # 检查是否为 ZIP
            if img.filename.lower().endswith(".zip"):
                import zipfile
                zip_path = os.path.join(session_dir, img.filename)
                with open(zip_path, "wb") as f:
                    content = await img.read()
                    f.write(content)
                # 解压
                try:
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        for info in zf.infolist():
                            if info.is_dir():
                                continue
                            if not is_image_file(info.filename):
                                continue
                            dest = os.path.join(session_dir, info.filename)
                            with zf.open(info) as src, open(dest, "wb") as dst:
                                dst.write(src.read())
                            saved_paths.append(dest)
                except Exception as exc:
                    logger.warning("ZIP 解压失败: %s", exc)
            elif is_image_file(img.filename):
                dest = os.path.join(session_dir, img.filename)
                with open(dest, "wb") as f:
                    content = await img.read()
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

        _review_results[result.id] = result

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
        dest = os.path.join(session_dir, img.filename)
        with open(dest, "wb") as f:
            content = await img.read()
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
    """获取免费额度"""
    # TODO: 对接实际额度管理系统
    return QuotaInfo(
        remaining=98,
        total=100,
        used_today=2,
    )


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
