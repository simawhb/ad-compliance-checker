# -*- coding: utf-8 -*-
"""驷马合规 · PDF 合规检测报告生成（基于 fpdf2）"""
import time
import os
import logging

logger = logging.getLogger(__name__)

_CHINESE_FONTS = [
    "C:/Windows/Fonts/simfang.ttf",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
]


def _find_font():
    for fp in _CHINESE_FONTS:
        if os.path.exists(fp):
            is_ttc = fp.lower().endswith(".ttc")
            logger.info(f"PDF 使用字体: {fp} (ttc={is_ttc})")
            return fp, is_ttc
    logger.warning("未找到中文字体，PDF 降级为纯文本")
    return None, False


def generate_pdf(text, result):
    try:
        from fpdf import FPDF
    except ImportError:
        logger.warning("fpdf2 未安装，降级为纯文本")
        return _text_report(result)

    font_path, is_ttc = _find_font()
    if not font_path:
        return _text_report(result)

    try:
        pdf = FPDF(format="A4")
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        kwargs = {"uni": True}
        if is_ttc:
            kwargs["ttc_index"] = 0
        pdf.add_font("Cn", "", font_path, **kwargs)

        pdf.set_font("Cn", "", 18)
        pdf.set_text_color(79, 106, 245)
        pdf.cell(0, 14, "驷马合规 · 广告合规检测报告", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Cn", "", 9)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(0, 8, f"生成时间: {time.strftime('%Y-%m-%d %H:%M')}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(8)

        score = result.get("score", 0)
        score_label = "合规" if score >= 80 else "存疑" if score >= 60 else "违规"
        score_color = (34, 197, 94) if score >= 80 else (245, 158, 11) if score >= 60 else (239, 68, 68)
        pdf.set_font("Cn", "", 14)
        pdf.set_text_color(*score_color)
        pdf.cell(0, 12, f"综合评分: {score} 分（{score_label}）", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        summary = result.get("summary", "检测完成")
        pdf.set_font("Cn", "", 10)
        pdf.set_text_color(13, 13, 13)
        pdf.multi_cell(0, 7, f"检测摘要: {summary}")
        pdf.ln(2)

        text_preview = (text[:300] + "……") if len(text) > 300 else text
        pdf.set_font("Cn", "", 10)
        pdf.multi_cell(0, 7, f"文案摘要: {text_preview}")
        pdf.ln(8)

        risks = result.get("risks", [])
        forbidden = [r for r in risks if r.get("type") in ("forbidden", "industry")]

        if not forbidden:
            pdf.set_font("Cn", "", 12)
            pdf.set_text_color(34, 197, 94)
            pdf.cell(0, 10, "✓ 未发现违规风险", new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_font("Cn", "", 12)
            pdf.set_text_color(26, 26, 46)
            pdf.cell(0, 10, f"违规风险清单（共 {len(forbidden)} 项）", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

            for i, risk in enumerate(forbidden[:30], 1):
                level = risk.get("risk_level", "low")
                label = {"critical": "违法", "high": "高危", "medium": "优化", "low": "提示"}.get(level, "提示")
                word = risk.get("word", "")
                category = risk.get("category", "")
                suggest = risk.get("suggest", "")
                law = risk.get("law", "")

                col = {"critical": (220, 38, 38), "high": (239, 68, 68),
                       "medium": (245, 158, 11), "low": (107, 114, 128)}.get(level, (107, 114, 128))
                pdf.set_text_color(*col)
                pdf.set_font("Cn", "", 9)
                pdf.cell(14, 7, f"[{label}]")
                pdf.set_text_color(13, 13, 13)
                pdf.set_font("Cn", "", 10)
                pdf.cell(0, 7, f"{i}.  \"{word}\"", new_x="LMARGIN", new_y="NEXT")

                indent = 15
                if category:
                    pdf.set_x(indent)
                    pdf.set_text_color(107, 114, 128)
                    pdf.set_font("Cn", "", 9)
                    pdf.cell(0, 5, f"类别: {category}", new_x="LMARGIN", new_y="NEXT")
                if suggest:
                    pdf.set_x(indent)
                    pdf.set_text_color(34, 197, 94)
                    pdf.set_font("Cn", "", 9)
                    pdf.cell(0, 5, f"建议: {suggest}", new_x="LMARGIN", new_y="NEXT")
                if law:
                    pdf.set_x(indent)
                    pdf.set_text_color(107, 114, 128)
                    pdf.set_font("Cn", "", 9)
                    pdf.cell(0, 5, f"依据: {law}", new_x="LMARGIN", new_y="NEXT")
                pdf.ln(3)

        pdf.ln(6)
        pdf.set_font("Cn", "", 8)
        pdf.set_text_color(156, 163, 175)
        pdf.cell(0, 6, "本报告由 AI 自动生成，仅供参考。重要文案建议由执业律师复核。", align="C")

        raw = pdf.output()
        if isinstance(raw, memoryview):
            raw = bytes(raw)
        elif isinstance(raw, bytearray):
            raw = bytes(raw)
        elif isinstance(raw, str):
            raw = raw.encode("utf-8")
        if raw[:4] == b"%PDF":
            logger.info(f"PDF 生成成功: {len(raw)} bytes")
            return raw
        logger.error(f"PDF 格式异常，降级为纯文本")
        return _text_report(result)
    except Exception as e:
        logger.exception(f"PDF 生成异常: {e}")
        return _text_report(result)


def _text_report(result):
    score = result.get("score", 0)
    risks = result.get("risks", [])
    summary = result.get("summary", "检测完成")
    lines = [
        "=" * 40,
        "驷马合规 · 广告合规检测报告",
        f"生成时间: {time.strftime('%Y-%m-%d %H:%M')}",
        f"综合评分: {score} 分",
        f"检测摘要: {summary}",
        "=" * 40, "",
    ]
    forbidden = [r for r in risks if r.get("type") in ("forbidden", "industry")]
    if forbidden:
        lines.append(f"违规风险清单（共 {len(forbidden)} 项）:")
        for i, risk in enumerate(forbidden, 1):
            lines.append(f'{i}.  "{risk.get("word", "")}"')
            if risk.get("category"):
                lines.append(f"   类别: {risk['category']}")
            if risk.get("suggest"):
                lines.append(f"   建议: {risk['suggest']}")
            if risk.get("law"):
                lines.append(f"   依据: {risk['law']}")
            lines.append("")
    else:
        lines.append("未发现违规风险。")
        lines.append("")
    lines.append("=" * 40)
    lines.append("本报告由 AI 自动生成，仅供参考。")
    return "\n".join(lines).encode("utf-8")
