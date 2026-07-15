"""
gaokao_spiders — Scrapy 项目设置

符合 RULES.md 的要求：
- DOWNLOAD_DELAY >= 2s
- 礼貌爬取，不对目标造成压力
- 输出 UTF-8 JSON Lines
"""

# === 爬虫名称 ===
BOT_NAME = "gaokao_spiders"
SPIDER_MODULES = ["gaokao_spiders.spiders"]
NEWSPIDER_MODULE = "gaokao_spiders.spiders"

# === 礼貌与反爬 ===
DOWNLOAD_DELAY = 3                # 请求间隔 ≥ 2s（RULES.md §1.1）
RANDOMIZE_DOWNLOAD_DELAY = True   # 随机延迟，更接近人类行为
CONCURRENT_REQUESTS = 2           # 低并发，不对目标造成压力
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# User-Agent（模拟浏览器，非 Scrapy 默认 UA）
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# === 重试与超时 ===
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 500, 502, 503, 504, 522, 524]
DOWNLOAD_TIMEOUT = 30

# === Cookie（教育部官网不需要登录，禁用 Cookie） ===
COOKIES_ENABLED = False

# === 管道 ===
# 院校爬虫直接输出到 JSONL，不经过数据库管道
# 后续可添加 PostgreSQL 管道
ITEM_PIPELINES = {}

# === 编码 ===
FEED_EXPORT_ENCODING = "utf-8"

# === 缓存（开发阶段启用，避免重复请求教育部） ===
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 86400  # 24小时
HTTPCACHE_DIR = "httpcache"
HTTPCACHE_IGNORE_HTTP_CODES = []

# === 日志 ===
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"

# === 测试模式（小规模验证） ===
# CLOSESPIDER_ITEMCOUNT = 10       # 开发时取消注释，只爬10条
# CLOSESPIDER_PAGECOUNT = 5        # 开发时取消注释，只爬5页

# === 自动限速（AutoThrottle） ===
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 3       # 初始延迟
AUTOTHROTTLE_MAX_DELAY = 10        # 最大延迟
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0  # 目标并发数

# === Telnet（开发调试用，生产关闭） ===
TELNETCONSOLE_ENABLED = False
