"""
手工上传适配器（方案 B — 兜底路径）

适用于反爬严重的平台（淘宝/天猫、拼多多、抖音小店），
用户通过上传截图/详情图/粘贴文字的方式提交内容。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from schemas import PlatformEnum, ProductData
from platform_adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


class ManualAdapter(BaseAdapter):
    """
    手工上传适配器 — 不需要 Playwright 页面对象，
    直接从用户提供的文件路径和文字创建 ProductData。
    """

    def __init__(self, text: str = "", platform: PlatformEnum = PlatformEnum.MANUAL):
        self._text = text
        self._platform = platform

    @property
    def platform(self) -> PlatformEnum:
        return self._platform

    @property
    def platform_name(self) -> str:
        return {
            PlatformEnum.MANUAL: "手工上传",
            PlatformEnum.TAOBAO: "淘宝/天猫",
            PlatformEnum.PINDUODUO: "拼多多",
            PlatformEnum.DOUYIN: "抖音小店",
        }.get(self._platform, "手工上传")

    # ──────────────────────────────────────────────
    # 页面加载（无操作，不适用）
    # ──────────────────────────────────────────────

    async def load(self, page, url: str):
        """手工上传模式不需要加载页面"""
        logger.info("手工上传模式：无需加载页面")
        pass

    # ──────────────────────────────────────────────
    # 提取
    # ──────────────────────────────────────────────

    async def extract(self, page=None) -> ProductData:
        """从用户提供的文字中提取商品信息"""
        product = ProductData(
            platform=self._platform,
            url="",
        )

        text = self._text.strip()
        if not text:
            return product

        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 标题启发式：商品标题通常包含品牌/产品名
            if not product.title and len(line) > 5:
                product.title = line
                break

        product.description = text
        return product

    # ──────────────────────────────────────────────
    # 图片
    # ──────────────────────────────────────────────

    async def download_images(self, page=None, output_dir: str = "") -> list[str]:
        """
        手工模式：图片已由用户上传，只需标准化处理

        Args:
            page: 不使用
            output_dir: 如果提供，将图片标准化后保存到此目录

        Returns:
            已上传图片路径列表（在 extract() 后被替换）
        """
        return []

    @staticmethod
    async def process_uploaded_images(
        image_paths: list[str],
        output_dir: str | Path,
    ) -> list[str]:
        """
        处理用户上传的图片：标准化 → OCR 准备

        Args:
            image_paths: 用户上传的图片路径列表
            output_dir: 输出目录

        Returns:
            标准化后的图片路径列表
        """
        from utils.image_utils import batch_standardize
        standardized = batch_standardize(image_paths, output_dir)
        return [str(p) for p in standardized]
