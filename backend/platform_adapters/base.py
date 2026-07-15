"""
平台适配器基类 — 所有电商平台的页面解析统一接口

每个平台适配器负责：
1. 加载页面（含反爬等待策略）
2. 提取结构化商品信息
3. 下载详情图片
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from schemas import PlatformEnum, ProductData


class BaseAdapter(ABC):
    """平台适配器基类"""

    @property
    @abstractmethod
    def platform(self) -> PlatformEnum:
        """返回平台枚举"""
        ...

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """返回平台可读名称"""
        ...

    # ──────────────────────────────────────────────
    # 核心接口
    # ──────────────────────────────────────────────

    @abstractmethod
    async def load(self, page, url: str):
        """
        加载页面，包含该平台特定的等待策略

        Args:
            page: Playwright Page 对象
            url: 商品页面 URL
        """
        ...

    @abstractmethod
    async def extract(self, page) -> ProductData:
        """
        从已加载的页面提取结构化商品信息

        Args:
            page: Playwright Page 对象

        Returns:
            ProductData 对象（不含 image_paths 和 screenshot_path）
        """
        ...

    @abstractmethod
    async def download_images(self, page, output_dir: str) -> list[str]:
        """
        下载商品详情图

        Args:
            page: Playwright Page 对象
            output_dir: 保存目录

        Returns:
            本地图片路径列表
        """
        ...

    # ──────────────────────────────────────────────
    # 辅助方法
    # ──────────────────────────────────────────────

    async def take_screenshot(self, page, output_path: str):
        """截取页面全屏截图"""
        await page.screenshot(path=output_path, full_page=True)

    def _sanitize_filename(self, text: str, max_len: int = 50) -> str:
        """清理文件名中的非法字符"""
        import re
        sanitized = re.sub(r'[\\/:*?"<>|]', "_", text)
        return sanitized[:max_len]
