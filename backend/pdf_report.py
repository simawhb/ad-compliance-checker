"""
PDF 报告生成 — 电商页面合规审查报告
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from schemas import ReviewResult, RiskLevel, ViolationSeverity

logger = logging.getLogger(__name__)


def generate_report(
    result: ReviewResult,
    output_path: str | Path,
    screenshot_path: Optional[str] = None,
):
    """
    生成电商合规审查 PDF 报告

    Args:
        result: 审查结果
        output_path: 输出 PDF 路径
        screenshot_path: 页面截图路径（可选）
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle",
        fontSize=20,
        leading=26,
        spaceAfter=12,
        alignment=1,  # center
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle",
        fontSize=14,
        leading=18,
        spaceBefore=16,
        spaceAfter=8,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1a56db"),
    ))
    styles.add(ParagraphStyle(
        name="ViolationTitle",
        fontSize=11,
        leading=14,
        spaceBefore=8,
        spaceAfter=4,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#dc2626"),
    ))
    styles.add(ParagraphStyle(
        name="Body",
        fontSize=10,
        leading=14,
        spaceAfter=4,
        fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        name="Small",
        fontSize=8,
        leading=10,
        textColor=colors.gray,
    ))

    elements = []

    # ── 标题 ──
    elements.append(Paragraph("驷马合规 · 电商页面审查报告", styles["ReportTitle"]))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        f"报告编号: {result.id} | 生成时间: {result.created_at.strftime('%Y-%m-%d %H:%M')}",
        styles["Small"],
    ))
    elements.append(Spacer(1, 12))

    # ── 风险等级 ──
    risk_color = {
        RiskLevel.HIGH: "#dc2626",
        RiskLevel.MEDIUM: "#ea580c",
        RiskLevel.LOW: "#16a34a",
    }.get(result.risk_level, "#6b7280")

    risk_text = f"<b>风险评估等级：<font color='{risk_color}'>{result.risk_level.value}</font></b>"
    elements.append(Paragraph(risk_text, styles["SectionTitle"]))

    # ── 页面信息摘要 ──
    elements.append(Paragraph("一、页面信息摘要", styles["SectionTitle"]))
    info_data = [
        ["审查渠道", "URL 自动抓取" if result.channel == "url" else "截图上传"],
        ["电商平台", result.platform.value],
        ["页面 URL", result.url or "（截图上传）"],
        ["页面摘要", result.page_summary],
    ]
    info_table = Table(info_data, colWidths=[4 * cm, 12 * cm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(info_table)

    # ── 违规点 ──
    elements.append(Paragraph("二、违规点详情", styles["SectionTitle"]))

    if not result.violation_items:
        elements.append(Paragraph("✓ 未发现违规项", styles["Body"]))
    else:
        # 按严重程度排序
        sorted_violations = sorted(
            result.violation_items,
            key=lambda v: (
                0 if v.severity == ViolationSeverity.CRITICAL
                else 1 if v.severity == ViolationSeverity.MEDIUM
                else 2
            ),
        )

        for i, v in enumerate(sorted_violations, 1):
            severity_color = {
                ViolationSeverity.CRITICAL: "#dc2626",
                ViolationSeverity.MEDIUM: "#ea580c",
                ViolationSeverity.MINOR: "#ca8a04",
            }.get(v.severity, "#6b7280")

            elements.append(Paragraph(
                f"违规 {i}：{v.dimension} "
                f"（<font color='{severity_color}'><b>{v.severity.value}</b></font>）",
                styles["ViolationTitle"],
            ))

            details = [
                ["违规原文", v.content],
                ["法律依据", v.law_basis],
                ["修改建议", v.suggestion],
            ]
            if v.penalty_reference:
                details.append(["处罚参考", v.penalty_reference])

            detail_table = Table(details, colWidths=[3 * cm, 13 * cm])
            detail_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#fef2f2")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#fecaca")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(detail_table)
            elements.append(Spacer(1, 8))

    # ── 审查结论 ──
    elements.append(Paragraph("三、审查结论", styles["SectionTitle"]))
    elements.append(Paragraph(result.summary, styles["Body"]))

    # ── 截图 ──
    if screenshot_path and os.path.exists(screenshot_path):
        elements.append(Paragraph("四、页面截图", styles["SectionTitle"]))
        try:
            img = Image(screenshot_path, width=14 * cm, height=10 * cm)
            elements.append(img)
        except Exception as exc:
            logger.warning("截图插入失败: %s", exc)

    # ── 页脚声明 ──
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        "本报告由 AI 自动生成，仅供合规参考，不构成法律意见。"
        "建议在做出最终决策前咨询专业律师。",
        styles["Small"],
    ))

    try:
        doc.build(elements)
        logger.info("PDF 报告生成成功: %s", output_path)
    except Exception as exc:
        logger.error("PDF 报告生成失败: %s", exc)
        raise
