"""
OCR 识别引擎 — PaddleOCR 主力 + easyocr 备用

工作模式：
1. 尝试 PaddleOCR（GPU 加速）
2. 若 PaddleOCR 不可用/失败，回退到 easyocr（CPU）
3. 支持单图识别和批量识别
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class OCREngine:
    """OCR 识别引擎封装"""

    def __init__(self, use_gpu: bool = True, fallback_to_easyocr: bool = True):
        self.use_gpu = use_gpu
        self.fallback_to_easyocr = fallback_to_easyocr
        self._paddle_ocr = None
        self._easy_ocr = None
        self._current_engine = None  # 'paddle' or 'easyocr'

    # ──────────────────────────────────────────────
    # 初始化
    # ──────────────────────────────────────────────

    def _init_paddle(self):
        """延迟初始化 PaddleOCR"""
        if self._paddle_ocr is not None:
            return True
        try:
            from paddleocr import PaddleOCR
            self._paddle_ocr = PaddleOCR(
                use_angle_cls=True,
                lang="ch",
                use_gpu=self.use_gpu,
                show_log=False,
                # GPU 内存不足时自动降级
                gpu_mem=6000 if self.use_gpu else 0,
            )
            self._current_engine = "paddle"
            logger.info("PaddleOCR 初始化成功 (GPU=%s)", self.use_gpu)
            return True
        except Exception as exc:
            logger.warning("PaddleOCR 初始化失败: %s", exc)
            self._paddle_ocr = None
            return False

    def _init_easyocr(self):
        """延迟初始化 easyocr（备用）"""
        if self._easy_ocr is not None:
            return True
        try:
            import easyocr
            self._easy_ocr = easyocr.Reader(
                ["ch_sim", "en"],
                gpu=self.use_gpu,
            )
            self._current_engine = "easyocr"
            logger.info("easyocr 初始化成功 (GPU=%s)", self.use_gpu)
            return True
        except Exception as exc:
            logger.warning("easyocr 初始化失败: %s", exc)
            self._easy_ocr = None
            return False

    # ──────────────────────────────────────────────
    # 核心识别方法
    # ──────────────────────────────────────────────

    def recognize(self, image_path: str | Path) -> str:
        """
        识别单张图片中的文字

        Args:
            image_path: 图片文件路径

        Returns:
            识别出的文字（按阅读顺序合并，用换行分隔）
        """
        start = time.time()

        # 尝试 PaddleOCR
        if self._init_paddle():
            try:
                result = self._paddle_ocr.ocr(str(image_path), cls=True)
                text = self._format_paddle_result(result)
                if text.strip():
                    elapsed = time.time() - start
                    logger.info(
                        "PaddleOCR 识别完成: %s (%d chars, %.1fs)",
                        image_path, len(text), elapsed,
                    )
                    return text
                logger.info("PaddleOCR 未识别出文字，尝试 easyocr...")
            except Exception as exc:
                logger.warning("PaddleOCR 识别失败: %s", exc)

        # 回退到 easyocr
        if self.fallback_to_easyocr and self._init_easyocr():
            try:
                result = self._easy_ocr.readtext(str(image_path))
                text = self._format_easyocr_result(result)
                elapsed = time.time() - start
                logger.info(
                    "easyocr 识别完成: %s (%d chars, %.1fs)",
                    image_path, len(text), elapsed,
                )
                return text
            except Exception as exc:
                logger.warning("easyocr 识别失败: %s", exc)

        logger.error("所有 OCR 引擎均识别失败: %s", image_path)
        return ""

    def recognize_batch(self, image_paths: list[str | Path]) -> list[str]:
        """
        批量识别多张图片

        Args:
            image_paths: 图片路径列表

        Returns:
            每张图的识别文字列表（顺序对应输入）
        """
        results: list[str] = []
        for i, path in enumerate(image_paths):
            logger.info("OCR 批量处理 [%d/%d]: %s", i + 1, len(image_paths), path)
            text = self.recognize(path)
            results.append(text)
        return results

    # ──────────────────────────────────────────────
    # 结果格式化
    # ──────────────────────────────────────────────

    @staticmethod
    def _format_paddle_result(result) -> str:
        """格式化 PaddleOCR 返回结果"""
        if not result or not result[0]:
            return ""
        # PaddleOCR 返回: list of list of (bbox, (text, confidence))
        lines = []
        for line in result[0]:
            text = line[1][0]
            confidence = line[1][1]
            if confidence > 0.3:  # 低置信度过滤
                lines.append(text)
        return "\n".join(lines)

    @staticmethod
    def _format_easyocr_result(result) -> str:
        """格式化 easyocr 返回结果"""
        if not result:
            return ""
        lines = []
        for bbox, text, confidence in result:
            if confidence > 0.3:
                lines.append(text)
        return "\n".join(lines)


# 全局单例
_engine: Optional[OCREngine] = None


def get_ocr_engine() -> OCREngine:
    """获取全局 OCR 引擎实例"""
    global _engine
    if _engine is None:
        _engine = OCREngine()
    return _engine
