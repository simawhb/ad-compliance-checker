"""
页面抓取引擎 — 电商产品页面内容抓取与 OCR 识别编排

核心流程：
1. 平台识别（从 URL 判断）
2. 获取对应适配器
3. Playwright 加载页面（含反爬策略）
4. 提取结构化字段
5. 下载详情图
6. OCR 识别图片文字
7. 合并所有文字内容输出
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from ocr_engine import OCREngine, get_ocr_engine
from platform_adapters import BaseAdapter, StandaloneAdapter, ManualAdapter
from schemas import PageData, PlatformEnum, ProductData
from utils.image_utils import ensure_temp_dir, standardize_image

logger = logging.getLogger(__name__)

# 尝试加载 JD 适配器（依赖可选）
try:
    from platform_adapters import JDAdapter
    _HAS_JD = JDAdapter is not None
except ImportError:
    _HAS_JD = False


# ═══════════════════════════════════════════════════
# 平台识别
# ═══════════════════════════════════════════════════

_PLATFORM_PATTERNS: list[tuple[re.Pattern, PlatformEnum]] = [
    # 京东
    (re.compile(r"https?://(item|product)\.jd\.com/"), PlatformEnum.JD),
    (re.compile(r"https?://(.*?)\.jd\.com/"), PlatformEnum.JD),
    # 淘宝/天猫
    (re.compile(r"https?://(item|detail)\.taobao\.com/"), PlatformEnum.TAOBAO),
    (re.compile(r"https?://(detail|item)\.tmall\.com/"), PlatformEnum.TAOBAO),
    # 拼多多
    (re.compile(r"https?://(mobile|m)\.yangkeduo\.com/"), PlatformEnum.PINDUODUO),
    (re.compile(r"https?://(.*?)\.pinduoduo\.com/"), PlatformEnum.PINDUODUO),
    # 抖音小店
    (re.compile(r"https?://(shop|vshop)\.douyin\.com/"), PlatformEnum.DOUYIN),
    (re.compile(r"https?://haohuo\.douyin\.com/"), PlatformEnum.DOUYIN),
]


def identify_platform(url: str) -> PlatformEnum:
    """从 URL 判断电商平台"""
    for pattern, platform in _PLATFORM_PATTERNS:
        if pattern.match(url):
            return platform
    return PlatformEnum.STANDALONE


def get_adapter(url: str) -> tuple[BaseAdapter, PlatformEnum]:
    """根据 URL 获取对应的平台适配器"""
    platform = identify_platform(url)

    if platform == PlatformEnum.JD and _HAS_JD:
        return JDAdapter(), platform
    elif platform in (PlatformEnum.TAOBAO, PlatformEnum.PINDUODUO, PlatformEnum.DOUYIN):
        # 强反爬平台：返回适配器但随后会触发兜底策略
        logger.warning("强反爬平台 %s，将尝试抓取并在失败时引导用户走方案B", platform.value)
        return StandaloneAdapter(), platform

    return StandaloneAdapter(), platform


# ═══════════════════════════════════════════════════
# 反爬策略
# ═══════════════════════════════════════════════════

async def apply_anti_scrape_strategies(page):
    """应用反爬规避策略"""
    # 1. 设置浏览器指纹
    await page.set_extra_http_headers({
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })

    # 2. 注入 WebDriver 检测规避
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        // 覆盖 Chrome 自动化特征
        window.chrome = { runtime: {} };
        // 覆盖权限查询
        const originalQuery = navigator.permissions.query;
        navigator.permissions.query = (params) => (
            params.name === 'notifications' ?
            Promise.resolve({ state: 'granted' }) :
            originalQuery(params)
        );
        // 覆盖 plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['zh-CN', 'zh', 'en']
        });
    """)


async def random_delay(min_sec: float = 2.0, max_sec: float = 5.0):
    """随机延迟，模拟人类行为"""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


# ═══════════════════════════════════════════════════
# 抓取结果（重试、兜底）
# ═══════════════════════════════════════════════════

class FetchResult:
    """抓取结果封装"""

    def __init__(
        self,
        success: bool,
        page_data: Optional[PageData] = None,
        error: str = "",
        needs_manual: bool = False,
    ):
        self.success = success
        self.page_data = page_data
        self.error = error
        self.needs_manual = needs_manual  # True = 建议用户走方案B


# ═══════════════════════════════════════════════════
# PageFetcher 主类
# ═══════════════════════════════════════════════════

class PageFetcher:
    """页面抓取引擎"""

    def __init__(self, ocr_engine: Optional[OCREngine] = None):
        self._ocr = ocr_engine or get_ocr_engine()
        self._browser = None
        self._lock = asyncio.Lock()

    # ──────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────

    async def fetch(self, url: str, max_retries: int = 3) -> FetchResult:
        """
        抓取产品页面完整内容

        流程：平台识别 → 加载页面 → 提取数据 → 下载图片 → OCR → 合并

        Args:
            url: 商品页面 URL
            max_retries: 最大重试次数

        Returns:
            FetchResult（含 PageData 或错误信息）
        """
        platform = identify_platform(url)

        # 强反爬平台直接建议方案B
        if platform in (PlatformEnum.TAOBAO, PlatformEnum.PINDUODUO, PlatformEnum.DOUYIN):
            return FetchResult(
                success=False,
                error=f"检测到 {platform.value} 为强反爬平台，自动抓取成功率极低。请使用「截图上传」模式提交。",
                needs_manual=True,
            )

        for attempt in range(1, max_retries + 1):
            try:
                result = await self._fetch_once(url, platform, attempt)
                if result.success:
                    return result
                if result.needs_manual:
                    return result  # 兜底提示，不重试
                logger.warning("抓取失败 [第%d次]: %s", attempt, result.error)
                if attempt < max_retries:
                    # 指数退避
                    wait = 2 ** attempt + random.uniform(0, 1)
                    await asyncio.sleep(wait)
            except Exception as exc:
                logger.error("抓取异常 [第%d次]: %s", attempt, exc)
                if attempt == max_retries:
                    return FetchResult(
                        success=False,
                        error=f"抓取失败（已重试{max_retries}次）: {exc}",
                    )

        return FetchResult(success=False, error="抓取失败（超出重试次数）")

    async def fetch_with_upload(
        self,
        image_paths: list[str],
        text: str = "",
    ) -> FetchResult:
        """
        通过上传截图/详情图方式获取内容（方案B）

        Args:
            image_paths: 用户上传的图片路径列表
            text: 用户手动粘贴的文字

        Returns:
            FetchResult
        """
        try:
            temp_dir = ensure_temp_dir()
            manual_adapter = ManualAdapter(text=text)

            # 处理上传图片：标准化 → OCR
            processed = await ManualAdapter.process_uploaded_images(image_paths, temp_dir)
            ocr_results = self._ocr.recognize_batch(processed)

            # 构建 PageData
            page_data = PageData(
                url="",
                platform=PlatformEnum.MANUAL,
                description=text,
                ocr_texts=ocr_results,
            )

            return FetchResult(success=True, page_data=page_data)

        except Exception as exc:
            logger.error("上传处理失败: %s", exc)
            return FetchResult(success=False, error=f"上传处理失败: {exc}")

    # ──────────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────────

    async def _fetch_once(
        self,
        url: str,
        platform: PlatformEnum,
        attempt: int,
    ) -> FetchResult:
        """单次抓取尝试"""
        adapter, _ = get_adapter(url)
        temp_dir = ensure_temp_dir()
        session_dir = os.path.join(temp_dir, f"session_{int(time.time())}_{attempt}")
        os.makedirs(session_dir, exist_ok=True)

        async with self._lock:  # 单实例串行化
            try:
                from playwright.async_api import async_playwright

                async with async_playwright() as pw:
                    # 启动浏览器
                    browser = await pw.chromium.launch(
                        headless=True,
                        args=[
                            "--no-sandbox",
                            "--disable-blink-features=AutomationControlled",
                            "--disable-dev-shm-usage",
                        ],
                    )
                    context = await browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                        locale="zh-CN",
                        timezone_id="Asia/Shanghai",
                    )
                    page = await context.new_page()

                    # 反爬策略
                    await apply_anti_scrape_strategies(page)

                    # 加载页面
                    await random_delay(2.0, 4.0)
                    await adapter.load(page, url)

                    # 检查是否触发验证码
                    page_content = await page.content()
                    if self._detect_captcha(page_content):
                        await browser.close()
                        return FetchResult(
                            success=False,
                            error="检测到验证码/反爬拦截，请使用「截图上传」模式",
                            needs_manual=True,
                        )

                    # 提取数据
                    product = await adapter.extract(page)

                    # 截图
                    screenshot_path = os.path.join(session_dir, "screenshot.png")
                    await adapter.take_screenshot(page, screenshot_path)

                    # 下载详情图
                    image_paths = await adapter.download_images(page, session_dir)

                    # OCR 识别
                    ocr_texts = self._ocr.recognize_batch(image_paths)

                    await browser.close()

                # 构建结果
                page_data = PageData(
                    url=url,
                    platform=platform,
                    title=product.title,
                    price=product.price,
                    params=product.params,
                    description=product.description,
                    ocr_texts=ocr_texts,
                    screenshot_path=screenshot_path,
                )

                logger.info(
                    "页面抓取成功: %s | 标题=%s | 价格=%s | 图片=%d | OCR段落=%d",
                    url,
                    product.title[:30] if product.title else "N/A",
                    product.price,
                    len(image_paths),
                    len(ocr_texts),
                )

                return FetchResult(success=True, page_data=page_data)

            except Exception as exc:
                error_msg = str(exc)
                # 检测常见 Playwright 错误
                if "Timeout" in error_msg:
                    return FetchResult(
                        success=False,
                        error="页面加载超时，请检查 URL 是否正确或使用「截图上传」模式",
                    )
                return FetchResult(success=False, error=error_msg)

    # ──────────────────────────────────────────────
    # 验证码检测
    # ──────────────────────────────────────────────

    @staticmethod
    def _detect_captcha(html: str) -> bool:
        """检测页面是否触发反爬/验证码"""
        indicators = [
            "验证码", "captcha", "CAPTCHA",
            "请完成安全验证", "安全验证",
            "您访问过于频繁", "访问受限",
            "checkForm", "needCheckCode",
            "人机验证", "滑动验证",
        ]
        for indicator in indicators:
            if indicator in html:
                return True
        return False


# 全局单例
_fetcher: Optional[PageFetcher] = None


def get_page_fetcher() -> PageFetcher:
    """获取全局 PageFetcher 实例"""
    global _fetcher
    if _fetcher is None:
        _fetcher = PageFetcher()
    return _fetcher
