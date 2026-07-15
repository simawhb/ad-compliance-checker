"""
京东适配器（P1 优先级）

解析京东商品详情页（item.jd.com / product.jd.com），
提取结构化商品信息并下载详情图。
"""

from __future__ import annotations

import logging
import os
import re
from urllib.parse import urlparse

from schemas import PlatformEnum, ProductData
from platform_adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


class JDAdapter(BaseAdapter):
    """京东商品页面适配器"""

    @property
    def platform(self) -> PlatformEnum:
        return PlatformEnum.JD

    @property
    def platform_name(self) -> str:
        return "京东"

    # ──────────────────────────────────────────────
    # 页面加载
    # ──────────────────────────────────────────────

    async def load(self, page, url: str):
        """加载京东商品页"""
        logger.info("京东适配器加载: %s", url)
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # 京东页面动态加载，等待关键元素
        try:
            await page.wait_for_selector(
                ".itemInfo-wrap, .product-intro, #itemInfo, .sku-name",
                timeout=15000,
            )
        except Exception:
            logger.warning("京东页面关键元素未出现，继续执行...")
        # 等待异步渲染
        await page.wait_for_timeout(3000)

    # ──────────────────────────────────────────────
    # 提取结构化数据
    # ──────────────────────────────────────────────

    async def extract(self, page) -> ProductData:
        """提取京东商品信息"""
        product = ProductData(
            platform=PlatformEnum.JD,
            url=page.url,
        )

        # 1. 标题
        title = await self._text(page, ".sku-name")
        if not title:
            title = await self._text(page, ".itemInfo-wrap .sku-name")
        product.title = title.strip() if title else ""

        # 2. 价格（京东价格动态加载，尝试多个选择器）
        price = await self._text(page, ".p-price .price")
        if not price:
            price = await self._text(page, ".summary-price .price")
        if not price:
            price = await self._text(page, '[class*="price"]')
        product.price = price.strip() if price else ""

        # 3. 参数
        params = {}
        # 京东参数在 .parameter2 或 .Ptable 中
        param_items = await page.query_selector_all(
            ".parameter2 li, "
            ".Ptable-item, "
            '[class*="parameter"] li'
        )
        for item in param_items:
            try:
                text = await item.inner_text()
                text = text.strip()
                if "：" in text:
                    key, value = text.split("：", 1)
                    params[key.strip()] = value.strip()
                elif ":" in text:
                    key, value = text.split(":", 1)
                    params[key.strip()] = value.strip()
            except Exception:
                continue
        product.params = params

        # 4. 描述（京东描述在 detail 区域）
        description = await self._text(page, ".detail-content")
        if not description:
            description = await self._text(page, "#product-detail")
        product.description = description.strip() if description else ""

        # 5. 原始 HTML
        product.raw_html = await page.content()

        return product

    # ──────────────────────────────────────────────
    # 下载详情图
    # ──────────────────────────────────────────────

    async def download_images(self, page, output_dir: str) -> list[str]:
        """下载京东商品主图与详情图"""
        import httpx

        os.makedirs(output_dir, exist_ok=True)
        image_paths: list[str] = []
        seen_urls: set[str] = set()

        # 主图轮播
        main_imgs = await page.query_selector_all(
            ".lh li img, "
            "#spec-list img, "
            '[class*="thumbs"] img, '
            ".preview img"
        )
        for img in main_imgs:
            src = await img.get_attribute("src") or await img.get_attribute("data-src")
            if not src:
                continue

            # 京东缩略图通常有 jpg 结尾，替换为更大尺寸
            src = src.replace("/s54x54_", "/n0_").replace("/s50x50_", "/n0_")
            src = re.sub(r"\.webp$", ".jpg", src)

            if src in seen_urls:
                continue
            seen_urls.add(src)
            src = self._normalize_url(src, page.url)
            path = await self._download(src, output_dir, f"jd_main_{len(image_paths)}.jpg")
            if path:
                image_paths.append(path)

        # 详情图（京东详情图片在 #product-detail 的 img 中）
        detail_imgs = await page.query_selector_all(
            "#product-detail img, "
            ".detail-content img, "
            ".detail-img img, "
            '[class*="detail"] img, '
            ".JD-detail img"
        )
        for img in detail_imgs:
            src = await img.get_attribute("src") or await img.get_attribute("data-src")
            if not src or src in seen_urls:
                continue
            # 过滤小图标
            try:
                w = await img.get_attribute("width")
                if w and int(w) < 100:
                    continue
            except Exception:
                pass
            seen_urls.add(src)
            src = self._normalize_url(src, page.url)
            path = await self._download(src, output_dir, f"jd_detail_{len(image_paths)}.jpg")
            if path:
                image_paths.append(path)

        return image_paths

    # ──────────────────────────────────────────────
    # 辅助方法
    # ──────────────────────────────────────────────

    async def _text(self, page, selector: str) -> str:
        """提取元素文本"""
        try:
            el = await page.query_selector(selector)
            if el:
                return (await el.inner_text()).strip()
        except Exception:
            pass
        return ""

    def _normalize_url(self, src: str, base_url: str) -> str:
        """补全图片 URL"""
        if src.startswith("//"):
            return "https:" + src
        if src.startswith("/"):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{src}"
        return src

    async def _download(self, url: str, output_dir: str, filename: str) -> str | None:
        """下载单张图片"""
        import httpx
        dest = os.path.join(output_dir, filename)
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    with open(dest, "wb") as f:
                        f.write(resp.content)
                    logger.info("京东图片下载: %s", filename)
                    return dest
        except Exception as exc:
            logger.warning("京东图片下载失败: %s — %s", url, exc)
        return None
