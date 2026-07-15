"""
独立站/企业官网适配器（P0 优先级）

通用型适配器，适用于 Shopify、WordPress WooCommerce 等主流建站系统，
以及各类企业官网。通过通用的 CSS 选择器和启发式规则提取信息。
"""

from __future__ import annotations

import logging
import os
import re
from urllib.parse import urlparse

from schemas import PlatformEnum, ProductData
from platform_adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


class StandaloneAdapter(BaseAdapter):
    """独立站/企业官网适配器"""

    @property
    def platform(self) -> PlatformEnum:
        return PlatformEnum.STANDALONE

    @property
    def platform_name(self) -> str:
        return "独立站/企业官网"

    # ──────────────────────────────────────────────
    # 页面加载
    # ──────────────────────────────────────────────

    async def load(self, page, url: str):
        """加载独立站页面"""
        logger.info("独立站适配器加载: %s", url)

        # 通用等待策略：等待主要内容出现
        await page.goto(url, wait_until="networkidle", timeout=30000)

        # 额外等待页面完全渲染
        await page.wait_for_timeout(2000)

        # 尝试关闭可能的弹窗/Cookie 横幅
        try:
            close_btns = await page.query_selector_all(
                'button:has-text("同意"), '
                'button:has-text("关闭"), '
                'button:has-text("Accept"), '
                '.cookie-close, '
                '[class*="close"]'
            )
            for btn in close_btns:
                if await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(500)
        except Exception:
            pass

    # ──────────────────────────────────────────────
    # 提取结构化数据
    # ──────────────────────────────────────────────

    async def extract(self, page) -> ProductData:
        """从独立站页面提取商品信息"""
        product = ProductData(
            platform=PlatformEnum.STANDALONE,
            url=page.url,
        )

        # 1. 标题 — 通用选择器 + meta 兜底
        title = await self._extract_text(page, [
            "h1[class*='product']",
            "h1[class*='title']",
            ".product-title",
            ".product-name",
            '[class*="productName"]',
            '[class*="product_title"]',
            'h1',
        ]) or await self._extract_meta(page, "og:title")
        product.title = title.strip() if title else ""

        # 2. 价格
        price = await self._extract_text(page, [
            '[class*="price"]',
            '[class*="Price"]',
            '.product-price',
            '.sale-price',
            '.regular-price',
            'span[class*="money"]',
            '[itemprop="price"]',
            '.current-price',
        ])
        product.price = price.strip() if price else ""

        # 3. 商品参数表
        params = await self._extract_params(page)
        product.params = params

        # 4. 描述文字
        description = await self._extract_text(page, [
            '[class*="description"]',
            '[class*="Description"]',
            '[class*="detail"]',
            '[class*="Detail"]',
            '.product-description',
            '.tab-content',
            '#description',
            '[itemprop="description"]',
        ])
        product.description = description.strip() if description else ""

        # 5. 原始 HTML（备用）
        product.raw_html = await page.content()

        return product

    # ──────────────────────────────────────────────
    # 下载详情图
    # ──────────────────────────────────────────────

    async def download_images(self, page, output_dir: str) -> list[str]:
        """下载独立站的商品图片"""
        from utils.image_utils import ensure_temp_dir
        import aiofiles  # noqa: F401
        import httpx

        os.makedirs(output_dir, exist_ok=True)
        image_paths: list[str] = []

        # 查找所有商品相关大图
        img_selectors = [
            '[class*="product"] img',
            '[class*="gallery"] img',
            '[class*="main-image"] img',
            '.woocommerce-product-gallery img',
            '[class*="swiper-slide"] img',
            'img[class*="product"]',
            'img[class*="main"]',
        ]

        seen_urls: set[str] = set()
        download_dir = output_dir
        domain = urlparse(page.url).netloc.replace(":", "_")

        for selector in img_selectors:
            imgs = await page.query_selector_all(selector)
            for img in imgs:
                src = await img.get_attribute("src") or await img.get_attribute("data-src")
                if not src or src in seen_urls:
                    continue

                # 过滤小图标（只下载大图）
                try:
                    natural_w = await img.get_attribute("naturalWidth")
                    if natural_w and int(natural_w) < 200:
                        continue
                except Exception:
                    pass

                seen_urls.add(src)

                # 补全 URL
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    parsed = urlparse(page.url)
                    src = f"{parsed.scheme}://{parsed.netloc}{src}"

                # 下载
                try:
                    filename = f"{domain}_img_{len(image_paths)}.jpg"
                    dest = os.path.join(download_dir, filename)

                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.get(src, follow_redirects=True)
                        if resp.status_code == 200:
                            with open(dest, "wb") as f:
                                f.write(resp.content)
                            image_paths.append(dest)
                            logger.info("下载图片: %s → %s", src, dest)
                except Exception as exc:
                    logger.warning("图片下载失败: %s — %s", src, exc)

                # 限制下载数量
                if len(image_paths) >= 20:
                    break

            if len(image_paths) >= 20:
                break

        return image_paths

    # ──────────────────────────────────────────────
    # 内部辅助方法
    # ──────────────────────────────────────────────

    async def _extract_text(self, page, selectors: list[str]) -> str:
        """从多个选择器中提取文本（命中即返回）"""
        for selector in selectors:
            try:
                el = await page.query_selector(selector)
                if el:
                    text = await el.inner_text()
                    if text and text.strip():
                        return text.strip()
            except Exception:
                continue
        return ""

    async def _extract_meta(self, page, meta_property: str) -> str:
        """提取 meta 标签内容"""
        try:
            el = await page.query_selector(f'meta[property="{meta_property}"]')
            if el:
                return await el.get_attribute("content") or ""
        except Exception:
            pass
        return ""

    async def _extract_params(self, page) -> dict[str, str]:
        """提取商品参数表"""
        params: dict[str, str] = {}

        # 尝试表格结构
        try:
            rows = await page.query_selector_all(
                '[class*="parameter"] tr, '
                '[class*="specification"] tr, '
                '.product-params tr, '
                'table[class*="spec"] tr, '
                'table[class*="param"] tr'
            )
            for row in rows:
                cells = await row.query_selector_all("td, th")
                if len(cells) >= 2:
                    key = (await cells[0].inner_text()).strip()
                    value = (await cells[1].inner_text()).strip()
                    if key and value:
                        params[key] = value
        except Exception:
            pass

        # 尝试定义列表
        if not params:
            try:
                dts = await page.query_selector_all(
                    '[class*="parameter"] dt, '
                    '[class*="specification"] dt, '
                    '.product-params dt'
                )
                dds = await page.query_selector_all(
                    '[class*="parameter"] dd, '
                    '[class*="specification"] dd, '
                    '.product-params dd'
                )
                for dt, dd in zip(dts, dds):
                    key = (await dt.inner_text()).strip()
                    value = (await dd.inner_text()).strip()
                    if key and value:
                        params[key] = value
            except Exception:
                pass

        return params
