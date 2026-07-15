#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gaokao-database API Server
驷马报考 — 高考志愿填报数据接口

监听 127.0.0.1:8000（可通过环境变量配置）
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# 加载 .env 环境变量（同时兼容系统环境变量）
# ---------------------------------------------------------------------------

# 先从 .env 文件读取（如果存在）
_env_path = Path(__file__).resolve().parents[2] / ".env"
if _env_path.exists():
    # 手动解析 .env，不依赖系统环境变量优先级
    _env_vars: Dict[str, str] = {}
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                _env_vars[_k.strip()] = _v.strip().strip("\"'")
    # 将 .env 的值写入 os.environ（优先于已存在的系统变量）
    for _k, _v in _env_vars.items():
        os.environ[_k] = _v

# 再通过 os.getenv 统一读取（此时系统变量已被 .env 覆盖）
load_dotenv(encoding="utf-8")

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------

BASE_DIR: Path = Path(__file__).resolve().parents[2]
STATIC_DIR: Path = Path(__file__).resolve().parent / "static"

# 数据库路径，优先从环境变量读取
_db_path_env = os.getenv("DB_PATH", "")
DB_PATH: Path = Path(_db_path_env).resolve() if _db_path_env else (BASE_DIR / "data" / "simadb" / "gaokao.db")

# ---------------------------------------------------------------------------
# DeepSeek API 配置（从环境变量读取，不再硬编码）
# ---------------------------------------------------------------------------

DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
_raw_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
# 兼容系统环境变量可能带了 /v1 后缀的情况，避免拼出 /v1/v1/
DEEPSEEK_BASE_URL: str = _raw_base_url[:-3] if _raw_base_url.endswith("/v1") else _raw_base_url
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

if not DEEPSEEK_API_KEY:
    print("[警告] DEEPSEEK_API_KEY 未设置。AI 问答功能将降级为纯数据库查询。")

# ---------------------------------------------------------------------------
# 服务器配置
# ---------------------------------------------------------------------------

HOST: str = os.getenv("HOST", "127.0.0.1")
PORT: int = int(os.getenv("PORT", "8000"))
RELOAD: bool = os.getenv("RELOAD", "false").lower() in ("true", "1", "yes")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info").lower()

# CORS 配置
_cors_origins = os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000")
CORS_ORIGINS: List[str] = [o.strip() for o in _cors_origins.split(",") if o.strip()]

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("gaokao-api")

# ---------------------------------------------------------------------------
# FastAPI 应用初始化
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期钩子：启动时输出配置信息，关闭时释放资源。"""
    logger.info("=" * 50)
    logger.info("  驷马报考 API Server 启动")
    logger.info(f"  数据库: {DB_PATH}")
    logger.info(f"  静态文件: {STATIC_DIR}")
    logger.info(f"  监听: {HOST}:{PORT}")
    logger.info(f"  Reload: {RELOAD}")
    logger.info(f"  CORS: {CORS_ORIGINS}")
    logger.info(f"  DeepSeek API Key: {'已配置' if DEEPSEEK_API_KEY else '未配置（AI 问答将降级）'}")
    logger.info("=" * 50)
    yield
    logger.info("驷马报考 API Server 关闭")


app = FastAPI(title="驷马报考 API", version="2.0.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# 全局异常处理（确保中文字符正确显示）
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常兜底：确保中文不乱码，不暴露敏感信息。"""
    logger.error(f"未捕获异常: {exc}", exc_info=True)
    return JSONResponse(
        content={"error": "服务暂时不可用，请稍后再试"},
        status_code=500,
        media_type="application/json; charset=utf-8",
    )


# ---------------------------------------------------------------------------
# CORS 中间件
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# ---------------------------------------------------------------------------
# 数据库连接池管理
# ---------------------------------------------------------------------------

# 线程安全的连接池：每个线程/协程各自持有连接
# 使用 contextvars 实现协程安全的上下文管理
import contextvars

_db_conn_var: contextvars.ContextVar[Optional[sqlite3.Connection]] = contextvars.ContextVar("db_conn", default=None)


def get_db() -> sqlite3.Connection:
    """获取当前上下文的数据库连接（每个请求/协程复用同一个连接）。

    使用 WAL 模式 + 合理的超时设置，避免并发读写冲突。
    连接由请求生命周期管理，请求结束后自动关闭。
    """
    conn = _db_conn_var.get()
    if conn is None:
        conn = sqlite3.connect(
            str(DB_PATH),
            timeout=10,            # 等待锁的超时时间（秒）
            check_same_thread=False if RELOAD else True,  # 开发模式允许多线程
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")   # 平衡性能与安全
        conn.execute("PRAGMA cache_size=-8000")      # 8MB 缓存
        conn.execute("PRAGMA foreign_keys=ON")
        _db_conn_var.set(conn)
    return conn


def close_db():
    """关闭当前上下文的数据库连接。"""
    conn = _db_conn_var.get()
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _db_conn_var.set(None)


# FastAPI 中间件：每个请求自动管理数据库连接生命周期
@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    """每个请求开始前准备数据库连接，请求结束后关闭。"""
    try:
        response = await call_next(request)
        return response
    finally:
        close_db()


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def row_to_dict(row: sqlite3.Row) -> Optional[Dict[str, Any]]:
    """单行转字典。"""
    return dict(row) if row else None


def rows_to_list(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    """多行转字典列表。"""
    return [dict(r) for r in rows]


def json_response(data: Any, status_code: int = 200) -> JSONResponse:
    """统一 JSON 响应，确保中文正确编码。"""
    return JSONResponse(
        content=data,
        status_code=status_code,
        media_type="application/json; charset=utf-8",
    )


def classify_sentiment(text: str) -> str:
    """简单关键词情感分析：positive / negative / neutral。"""
    if not text:
        return "neutral"
    positive_words = [
        "好", "优秀", "棒", "喜欢", "推荐", "不错", "满意", "强",
        "厉害", "牛", "顶", "赞", "好评", "靠谱", "良心", "一流",
        "顶尖", "出色", "完美", "值得", "首选", "热门", "就业好",
    ]
    negative_words = [
        "差", "烂", "坑", "后悔", "失望", "垃圾", "不行", "水",
        "弱", "恶心", "黑", "差评", "坑爹", "骗钱", "浪费", "别来",
        "很差", "不好", "糟", "惨", "坑人",
    ]
    pos = sum(1 for w in positive_words if w in text)
    neg = sum(1 for w in negative_words if w in text)
    if pos > neg:
        return "positive"
    elif neg > pos:
        return "negative"
    return "neutral"


def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """安全地将值转换为 int。"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """安全地将值转换为 float。"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def strip_markdown(text: str) -> str:
    """去除 Markdown 格式符号，保留纯文本内容。

    移除：
      - **加粗** / __加粗__
      - *斜体* / _斜体_
      - # 标题
      - ``` 代码块 ``` / `行内代码`
      - - 无序列表 / * 无序列表
      - 1. 有序列表
      - --- 分隔线
      - > 引用
      - [文本](链接) → 文本
      - ![文本](链接) → 文本
    """
    if not text:
        return text

    # 1. 图片 ![alt](url) → alt
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)
    # 2. 链接 [text](url) → text
    text = re.sub(r'\[([^\]]*)\]\([^)]+\)', r'\1', text)
    # 3. 代码块 ```...```
    text = re.sub(r'```[\s\S]*?```', '', text)
    # 4. 行内代码 `code`
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # 5. 标题 # ~ ######
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # 6. 加粗 **text** 和 __text__
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    # 7. 斜体 *text* 和 _text_（小心不要误伤中文_）
    text = re.sub(r'(?<!\*)\*(?!\*)([^*]+)\*(?!\*)', r'\1', text)
    text = re.sub(r'(?<!_)_(?!_)([^_]+)_(?!_)', r'\1', text)
    # 8. 无序列表 - 和 * 开头
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    # 9. 有序列表 1. 2. 开头
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    # 10. 引用 >
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)
    # 11. 分隔线 ---
    text = re.sub(r'\n[\s]*-{3,}[\s]*\n', '\n', text)
    # 12. 清理多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 13. 清理首尾空白
    text = text.strip()

    return text


def format_chinese_paragraph(text: str) -> str:
    """中文段落排版：每个段落首行缩进两个全角空格（　　）。

    同时检测段落开头的"标题句"（如"专业内容。"、"就业前景。"），
    用【】包裹使其在视觉上突出。

    段落以双换行 \n\n 分隔。
    """
    if not text:
        return text
    paragraphs = text.split('\n\n')
    formatted = []
    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            continue
        # 检测段落开头的标题句：短句（2-10个字符）以。或：结尾，后接更多内容
        # 匹配模式：开头的2-10个中文字符/字母，以 。或 ：结束
        heading = re.match(
            r'^([^，；,;。：\n]{2,10}[。：])\s*(.+)',
            stripped,
        )
        if heading:
            title = heading.group(1).strip()
            rest = heading.group(2).strip()
            formatted.append(f'　　【{title}】{rest}')
        else:
            formatted.append('　　' + stripped)
    return '\n\n'.join(formatted)


# ---------------------------------------------------------------------------
# 限流器（用于 DeepSeek API 调用）
# ---------------------------------------------------------------------------

class RateLimiter:
    """简单的令牌桶限流器。"""

    def __init__(self, max_calls: int = 10, period: float = 60.0):
        self.max_calls = max_calls
        self.period = period
        self.calls: List[float] = []

    def acquire(self) -> float:
        """获取调用许可。返回等待时间（秒），0 表示无需等待。"""
        now = time.monotonic()
        # 清理过期的记录
        self.calls = [t for t in self.calls if now - t < self.period]

        if len(self.calls) >= self.max_calls:
            # 需要等待
            wait = self.calls[0] + self.period - now
            if wait > 0:
                return wait

        self.calls.append(now)
        return 0.0


# DeepSeek API 限流器：每分钟最多 10 次调用
deepseek_limiter = RateLimiter(max_calls=10, period=60.0)


# ---------------------------------------------------------------------------
# 1. GET /api/schools/search
# ---------------------------------------------------------------------------

@app.get("/api/schools/search")
def schools_search(q: str = Query("", description="搜索关键词")):
    """按学校名称模糊搜索。"""
    if not q or len(q.strip()) < 1:
        return json_response({"schools": []})

    conn = get_db()
    try:
        cur = conn.execute(
            "SELECT seq, name, code_edu, admin_department, location, level, remarks "
            "FROM schools WHERE name LIKE ? LIMIT 50",
            (f"%{q.strip()}%",),
        )
        rows = cur.fetchall()
        return json_response({"schools": rows_to_list(rows)})
    except Exception as e:
        logger.error(f"schools_search 异常: {e}")
        return json_response({"error": "查询失败", "schools": []}, 500)


# ---------------------------------------------------------------------------
# 2. GET /api/admission/query
# ---------------------------------------------------------------------------

@app.get("/api/admission/query")
def admission_query(
    school_name: str = Query(None),
    major_name: str = Query(None),
    province: str = Query(None),
    year: int = Query(None),
    batch: str = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """录取数据多条件查询。"""
    conditions: List[str] = []
    params: List[Any] = []

    if school_name:
        conditions.append("school_name LIKE ?")
        params.append(f"%{school_name.strip()}%")
    if major_name:
        conditions.append("major_name LIKE ?")
        params.append(f"%{major_name.strip()}%")
    if province:
        conditions.append("province = ?")
        params.append(province.strip())
    if year is not None:
        conditions.append("year = ?")
        params.append(year)
    if batch:
        conditions.append("batch = ?")
        params.append(batch.strip())

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    sql = (
        f"SELECT school_id, school_name, major_name, batch, plan_count, "
        f"admit_score_min, admit_rank_min, year, province, data_source, data_confidence "
        f"FROM admission WHERE {where_clause} ORDER BY admit_score_min DESC "
        f"LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])

    conn = get_db()
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()

        # 总数
        count_sql = f"SELECT COUNT(*) FROM admission WHERE {where_clause}"
        count_cur = conn.execute(count_sql, params[:-2])
        total = count_cur.fetchone()[0]

        return json_response({
            "total": total,
            "limit": limit,
            "offset": offset,
            "data": rows_to_list(rows),
        })
    except Exception as e:
        logger.error(f"admission_query 异常: {e}")
        return json_response({"error": "查询失败", "data": []}, 500)


# ---------------------------------------------------------------------------
# 3. GET /api/admission/rank
# ---------------------------------------------------------------------------

@app.get("/api/admission/rank")
def admission_rank(
    score: float = Query(None),
    rank: int = Query(None),
    province: str = Query(None),
    year: int = Query(None),
    limit: int = Query(30, ge=1, le=200),
):
    """位次/分数模式查询。

    rank 模式：按 ABS(admit_rank_min - ?) 排序。
    score 模式：筛选 <= 分数的记录，按分数降序。
    """
    conditions: List[str] = []
    params: List[Any] = []

    if province:
        conditions.append("province = ?")
        params.append(province.strip())
    if year is not None:
        conditions.append("year = ?")
        params.append(year)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    if rank is not None:
        order_by = "ABS(admit_rank_min - ?) ASC"
        order_params = [rank]
        sql = (
            f"SELECT school_id, school_name, major_name, batch, plan_count, "
            f"admit_score_min, admit_rank_min, year, province, data_source, data_confidence "
            f"FROM admission WHERE {where_clause} AND admit_rank_min IS NOT NULL "
            f"ORDER BY {order_by} LIMIT ?"
        )
        params = params + order_params + [limit]
    elif score is not None:
        conditions.append("admit_score_min <= ?")
        params.append(score)
        where_clause = " AND ".join(conditions)
        sql = (
            f"SELECT school_id, school_name, major_name, batch, plan_count, "
            f"admit_score_min, admit_rank_min, year, province, data_source, data_confidence "
            f"FROM admission WHERE {where_clause} "
            f"ORDER BY admit_score_min DESC LIMIT ?"
        )
        params.append(limit)
    else:
        return json_response({"error": "请提供 score 或 rank 参数"}, 400)

    conn = get_db()
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        data = rows_to_list(rows)

        # 冲稳保分层（仅 score 模式）
        tiers = {"冲": 0, "稳": 0, "保": 0}
        if score is not None:
            for r in data:
                s = r.get("admit_score_min")
                if s is not None:
                    if s > score - 10:
                        tiers["冲"] += 1
                    elif s > score - 30:
                        tiers["稳"] += 1
                    else:
                        tiers["保"] += 1

        return json_response({
            "data": data,
            "mode": "rank" if rank is not None else "score",
            "tiers": tiers,
        })
    except Exception as e:
        logger.error(f"admission_rank 异常: {e}")
        return json_response({"error": "查询失败", "data": []}, 500)


# ---------------------------------------------------------------------------
# 4. GET /api/major/detail
# ---------------------------------------------------------------------------

@app.get("/api/major/detail")
def major_detail(
    major: str = Query(..., description="专业名称"),
    province: str = Query(None),
    year: int = Query(None),
):
    """专业详情：录取统计 + 口碑 + 薪资。"""
    if not major.strip():
        return json_response({"error": "请提供 major 参数"}, 400)

    conn = get_db()
    try:
        major_pattern = f"%{major.strip()}%"

        # 录取统计
        adm_query = (
            "SELECT province, year, COUNT(*) as school_count, "
            "MIN(admit_score_min) as min_score, MAX(admit_score_min) as max_score, "
            "ROUND(AVG(admit_score_min), 1) as avg_score "
            "FROM admission WHERE major_name LIKE ?"
        )
        adm_params: List[Any] = [major_pattern]
        if province:
            adm_query += " AND province = ?"
            adm_params.append(province)
        if year is not None:
            adm_query += " AND year = ?"
            adm_params.append(year)
        adm_query += " GROUP BY province, year ORDER BY year DESC, province"

        adm_cur = conn.execute(adm_query, adm_params)
        admission_stats = rows_to_list(adm_cur.fetchall())

        # 口碑（forum 表，按学校关联）
        rep_query = (
            "SELECT f.platform, f.title, f.content_text, f.like_count, f.reply_count, "
            "f.publish_time, f.school_id, f.platform_url "
            "FROM forum f "
            "INNER JOIN admission a ON f.school_id = a.school_id "
            "WHERE a.major_name LIKE ?"
        )
        rep_params: List[Any] = [major_pattern]
        if province:
            rep_query += " AND a.province = ?"
            rep_params.append(province)
        rep_query += " ORDER BY f.like_count DESC LIMIT 20"

        rep_cur = conn.execute(rep_query, rep_params)
        forum_rows = rep_cur.fetchall()
        reputation_list: List[Dict[str, Any]] = []
        for r in forum_rows:
            d = dict(r)
            d["sentiment"] = classify_sentiment(d.get("content_text", ""))
            reputation_list.append(d)

        # 薪资
        salary_cur = conn.execute(
            "SELECT city, keyword, count, salary_min, salary_max FROM jobs WHERE keyword LIKE ? LIMIT 20",
            (major_pattern,),
        )
        salary_list = rows_to_list(salary_cur.fetchall())

        # 适配前端期望的数据结构
        adm_stat = admission_stats[0] if admission_stats else {}
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        for r in reputation_list:
            s = r.get("sentiment", "neutral")
            sentiment_counts[s] = sentiment_counts.get(s, 0) + 1
        total_sentiment = sum(sentiment_counts.values())
        sentiment_pct = {
            k: round(v / total_sentiment * 100, 1) if total_sentiment > 0 else 0
            for k, v in sentiment_counts.items()
        }

        return json_response({
            "major": major.strip(),
            "province": province or "全国",
            "year": year or "全部",
            "admission_stats": {
                "count": adm_stat.get("school_count", 0),
                "max_score": adm_stat.get("max_score", 0),
                "avg_score": adm_stat.get("avg_score", 0),
                "min_score": adm_stat.get("min_score", 0),
            },
            "admissions": [],  # 前端用此字段展示院校列表，暂留空
            "sentiment": {
                "total": total_sentiment,
                "positive": sentiment_pct.get("positive", 0),
                "neutral": sentiment_pct.get("neutral", 0),
                "negative": sentiment_pct.get("negative", 0),
                "details": {"positive": [], "negative": []},
            },
            "salaries": salary_list,
        })
    except Exception as e:
        logger.error(f"major_detail 异常: {e}")
        return json_response({"error": "查询失败"}, 500)


# ---------------------------------------------------------------------------
# 5. GET /api/reputation/{school_name}
# ---------------------------------------------------------------------------

@app.get("/api/reputation/{school_name}")
def reputation(school_name: str):
    """学校口碑：forum 表 + 情感分析。"""
    conn = get_db()
    try:
        # 先通过学校名找到对应的教育代码
        school_cur = conn.execute(
            "SELECT code_edu FROM schools WHERE name LIKE ? OR name LIKE ?",
            (f"%{school_name}%", f"{school_name}%"),
        )
        school_codes = [row[0] for row in school_cur.fetchall() if row[0]]
        
        # 构建查询条件：匹配已知的学校代码 + 标题中包含学校名
        posts: List[Dict[str, Any]] = []
        if school_codes:
            # 构造 IN 查询
            placeholders = ",".join(["?" for _ in school_codes])
            query = f"""
                SELECT platform, thread_id, title, content_text, platform_url,
                       author_id, view_count, like_count, reply_count, publish_time,
                       quality_score, summary, school_id
                FROM forum WHERE school_id IN ({placeholders}) OR title LIKE ?
                ORDER BY like_count DESC LIMIT 50
            """
            params = school_codes + [f"%{school_name}%"]
        else:
            # 如果没找到学校代码，只按标题匹配
            query = """
                SELECT platform, thread_id, title, content_text, platform_url,
                       author_id, view_count, like_count, reply_count, publish_time,
                       quality_score, summary, school_id
                FROM forum WHERE title LIKE ?
                ORDER BY like_count DESC LIMIT 50
            """
            params = [f"%{school_name}%"]
        
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        
        sentiments: Dict[str, int] = {"positive": 0, "negative": 0, "neutral": 0}
        for r in rows:
            d = dict(r)
            sent = classify_sentiment(d.get("content_text", ""))
            d["sentiment"] = sent
            sentiments[sent] += 1
            posts.append(d)

        return json_response({
            "school_name": school_name,
            "total_posts": len(posts),
            "sentiment_summary": sentiments,
            "posts": posts,
        })
    except Exception as e:
        logger.error(f"reputation 异常: {e}")
        return json_response({"error": "查询失败", "posts": []}, 500)


# ---------------------------------------------------------------------------
# 6. GET /api/job/salary
# ---------------------------------------------------------------------------

@app.get("/api/job/salary")
def job_salary(
    major: str = Query(None),
    city: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """岗位薪资查询。"""
    conditions: List[str] = []
    params: List[Any] = []

    if major:
        conditions.append("keyword LIKE ?")
        params.append(f"%{major.strip()}%")
    if city:
        conditions.append("city LIKE ?")
        params.append(f"%{city.strip()}%")

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT city, keyword, count, salary_min, salary_max FROM jobs WHERE {where_clause} LIMIT ?"
    params.append(limit)

    conn = get_db()
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        return json_response({"data": rows_to_list(rows)})
    except Exception as e:
        logger.error(f"job_salary 异常: {e}")
        return json_response({"error": "查询失败", "data": []}, 500)


# ---------------------------------------------------------------------------
# 7. GET /api/control-lines
# ---------------------------------------------------------------------------

@app.get("/api/control-lines")
def control_lines(
    province: str = Query(None),
    year: int = Query(None),
):
    """省控线查询（从数据库读取，不再硬编码）。"""
    conditions: List[str] = []
    params: List[Any] = []

    if province:
        conditions.append("province = ?")
        params.append(province.strip())
    if year is not None:
        conditions.append("year = ?")
        params.append(year)

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    sql = (
        f"SELECT id, province, year, batch, category, score "
        f"FROM control_lines WHERE {where_clause} "
        f"ORDER BY year DESC, province, batch"
    )

    conn = get_db()
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        return json_response({"data": rows_to_list(rows)})
    except Exception as e:
        logger.error(f"control_lines 异常: {e}")
        return json_response({"error": "查询失败", "data": []}, 500)


# ---------------------------------------------------------------------------
# 8. GET /api/holland/questions
# ---------------------------------------------------------------------------

@app.get("/api/holland/questions")
def holland_questions():
    """返回霍兰德 6 题精简版测试题。"""
    questions = [
        {
            "id": 1,
            "question": "你更喜欢做哪类事情？",
            "options": [
                {"code": "R", "label": "动手修理、组装、户外活动"},
                {"code": "I", "label": "做实验、研究问题、分析数据"},
            ],
        },
        {
            "id": 2,
            "question": "你更擅长什么？",
            "options": [
                {"code": "A", "label": "画画、写作、音乐、表演"},
                {"code": "S", "label": "与人沟通、帮助别人、教书"},
            ],
        },
        {
            "id": 3,
            "question": "你在团队中通常扮演什么角色？",
            "options": [
                {"code": "E", "label": "组织者、决策者、带头人"},
                {"code": "C", "label": "执行者、核对者、按计划做事"},
            ],
        },
        {
            "id": 4,
            "question": "你更喜欢什么工作环境？",
            "options": [
                {"code": "R", "label": "户外、车间、实验室"},
                {"code": "A", "label": "工作室、创意空间、自由环境"},
            ],
        },
        {
            "id": 5,
            "question": "你更看重工作的什么方面？",
            "options": [
                {"code": "I", "label": "探索新知识、解决难题"},
                {"code": "S", "label": "帮助他人、对社会有贡献"},
            ],
        },
        {
            "id": 6,
            "question": "你做事的风格是？",
            "options": [
                {"code": "E", "label": "果断决策、争取资源、推动进展"},
                {"code": "C", "label": "仔细核对、按流程走、追求准确"},
            ],
        },
    ]
    return json_response({"questions": questions})


# ---------------------------------------------------------------------------
# 9. POST /api/holland/quiz
# ---------------------------------------------------------------------------

@app.post("/api/holland/quiz")
async def holland_quiz(request: Request):
    """提交霍兰德测试答案。"""
    try:
        body = await request.json()
        answers = body.get("answers", [])
        if not isinstance(answers, list) or len(answers) == 0:
            return json_response({"error": "请提供 answers 数组"}, 400)

        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from holland import calculate_holland
        result = calculate_holland(answers)
        return json_response(result)
    except Exception as e:
        logger.error(f"holland_quiz 异常: {e}")
        return json_response({"error": "分析失败"}, 500)


# ---------------------------------------------------------------------------
# 10. GET /api/subject/combinations + GET /api/subject/match
# ---------------------------------------------------------------------------

@app.get("/api/subject/combinations")
def subject_combinations():
    """获取全部 12 种选科组合及可报比例排名。"""
    try:
        _subj_dir = str(Path(__file__).resolve().parent.parent / 'crawler' / 'gaokao_spiders' / 'spiders' / 'majors')
        sys.path.insert(0, _subj_dir)
        from subject_selector import rank_combinations
        ranked = rank_combinations()
        return json_response({"combinations": ranked})
    except Exception as e:
        logger.error(f"subject_combinations 异常: {e}")
        return json_response({"error": "查询失败", "combinations": []}, 500)


@app.get("/api/subject/match")
def subject_match(code: str = Query(..., description="选科组合编码，如 物化生")):
    """查询某个选科组合的详细信息。"""
    if not code.strip():
        return json_response({"error": "请提供 code 参数"}, 400)
    try:
        _subj_dir = str(Path(__file__).resolve().parent.parent / 'crawler' / 'gaokao_spiders' / 'spiders' / 'majors')
        sys.path.insert(0, _subj_dir)
        from subject_selector import get_combination_info
        info = get_combination_info(code.strip())
        if info is None:
            return json_response({"error": f"未找到组合: {code}"}, 404)
        return json_response(info)
    except Exception as e:
        logger.error(f"subject_match 异常: {e}")
        return json_response({"error": "查询失败"}, 500)


# ---------------------------------------------------------------------------
# 11. POST /api/ask — AI 问答（带限流和降级）
# ---------------------------------------------------------------------------

@app.post("/api/ask")
async def ask_deepseek(request: Request):
    """调用 DeepSeek API 回答问题，降级时展示数据库上下文。"""
    db_context = ""  # 提前初始化，避免异常处理时 UnboundLocalError
    try:
        body = await request.json()
        question = (body.get("question") or "").strip()
        if not question:
            return json_response({"error": "请提供 question"}, 400)

        # 收集数据库上下文
        conn = get_db()
        db_context = _build_db_context(conn, question)

        # 如果没有配置 API Key，直接降级
        if not DEEPSEEK_API_KEY:
            return json_response({
                "answer": format_chinese_paragraph(strip_markdown(
                    "AI 问答功能暂未配置 API Key。\n\n"
                    f"以下是与您问题相关的数据库查询结果，供参考：\n\n{db_context}"
                )),
                "source": "fallback_no_key",
            })

        # 限流检查
        wait_time = deepseek_limiter.acquire()
        if wait_time > 0:
            logger.warning(f"DeepSeek API 限流触发，需等待 {wait_time:.1f} 秒")
            return json_response({
                "answer": format_chinese_paragraph(strip_markdown(
                    f"⚠️ 当前 AI 服务请求过多，请稍后再试。\n\n"
                    f"以下是与您问题相关的数据库查询结果，供参考：\n\n{db_context}"
                )),
                "source": "rate_limited",
            })

        # 构建 system prompt
        system_prompt = (
            "你是高考志愿填报助手。你可以根据提供的数据库上下文帮助用户解答问题。\n\n"
            "数据库上下文（来自 gaokao.db）：\n"
            f"{db_context}\n\n"
            "请用中文回答，简洁、准确。如果数据库上下文不足以回答，请如实告知，"
            "并提供你的一般性建议。\n\n"
            "重要格式要求：回答中不要使用任何 Markdown 格式符号。"
            "不要使用**加粗**、*斜体*、#标题、-列表、```代码块等。"
            "使用纯文字叙述即可。如果有列举项，用段落文字或简单的123序号描述。"
        )

        # 尝试调用 DeepSeek（带超时和重试）
        max_retries = 2
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                        },
                        json={
                            "model": DEEPSEEK_MODEL,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": question},
                            ],
                            "temperature": 0.7,
                            "max_tokens": 1024,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_answer = data["choices"][0]["message"]["content"]
                        answer = format_chinese_paragraph(strip_markdown(raw_answer))
                        return json_response({
                            "answer": answer,
                            "source": "deepseek",
                        })
                    elif resp.status_code == 429 and attempt < max_retries - 1:
                        # 限流，等待后重试
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        raise Exception(f"DeepSeek API 返回 {resp.status_code}")
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                raise

        raise Exception(f"DeepSeek API 调用失败（重试 {max_retries} 次）")

    except Exception as e:
        logger.warning(f"AI 问答降级: {e}")
        # 降级：返回数据库上下文
        return json_response({
            "answer": format_chinese_paragraph(strip_markdown(
                f"AI 服务暂时不可用。\n\n"
                f"以下是与您问题相关的数据库查询结果，供参考：\n\n{db_context}"
            )),
            "source": "fallback",
        })


# 为了 async sleep，需要导入 asyncio
import asyncio


def _build_db_context(conn: sqlite3.Connection, question: str) -> str:
    """根据用户问题构建数据库上下文摘要。"""
    parts: List[str] = []

    # 提取可能的关键词
    keywords = re.findall(r"[一-鿿\w]+", question)

    # 学校信息
    try:
        for kw in keywords[:3]:
            cur = conn.execute(
                "SELECT name, location, level FROM schools WHERE name LIKE ? LIMIT 5",
                (f"%{kw}%",),
            )
            rows = cur.fetchall()
            if rows:
                parts.append(f"【学校信息】匹配'{kw}'：")
                for r in rows:
                    parts.append(f"  - {r['name']}（{r['location']}，{r['level']}）")
    except Exception:
        pass

    # 录取数据
    try:
        for kw in keywords[:3]:
            cur = conn.execute(
                "SELECT school_name, major_name, admit_score_min, admit_rank_min, year, province, batch "
                "FROM admission WHERE school_name LIKE ? OR major_name LIKE ? LIMIT 10",
                (f"%{kw}%", f"%{kw}%"),
            )
            rows = cur.fetchall()
            if rows:
                parts.append(f"【录取数据】匹配'{kw}'：")
                for r in rows:
                    parts.append(
                        f"  - {r['school_name']} / {r['major_name']} "
                        f"（{r['year']}年 {r['province']} {r['batch']}）"
                        f" 最低分={r['admit_score_min']} 最低位次={r['admit_rank_min']}"
                    )
    except Exception:
        pass

    # 省控线
    try:
        cur = conn.execute(
            "SELECT province, year, batch, category, score FROM control_lines ORDER BY year DESC LIMIT 20"
        )
        rows = cur.fetchall()
        if rows:
            parts.append("【省控线】最近数据：")
            for r in rows:
                parts.append(f"  - {r['province']} {r['year']}年 {r['category']} {r['batch']}：{r['score']}分")
    except Exception:
        pass

    # 薪资
    try:
        for kw in keywords[:2]:
            cur = conn.execute(
                "SELECT city, keyword, salary_min, salary_max, count FROM jobs WHERE keyword LIKE ? LIMIT 5",
                (f"%{kw}%",),
            )
            rows = cur.fetchall()
            if rows:
                parts.append(f"【薪资数据】匹配'{kw}'：")
                for r in rows:
                    parts.append(f"  - {r['city']} {r['keyword']}：¥{r['salary_min']}-{r['salary_max']}k（{r['count']}个样本）")
    except Exception:
        pass

    if not parts:
        # 返回全局概览
        try:
            cur = conn.execute("SELECT COUNT(*) FROM schools")
            school_count = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM admission")
            adm_count = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(DISTINCT province) FROM admission")
            provinces_count = len([r[0] for r in cur.fetchall()])
            cur = conn.execute("SELECT COUNT(*) FROM jobs")
            job_count = cur.fetchone()[0]
            parts.append(
                f"【数据库概览】\n"
                f"  - 学校总数：{school_count}\n"
                f"  - 录取记录：{adm_count}\n"
                f"  - 覆盖省份：{provinces_count}\n"
                f"  - 薪资数据：{job_count}"
            )
        except Exception:
            parts.append("【数据库概览】暂时无法获取。")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 12. GET /api/monitor/data-health
# ---------------------------------------------------------------------------

@app.get("/api/monitor/data-health")
def monitor_data_health(days: int = Query(7, ge=1, le=30)):
    """最近 N 天采集状态。"""
    conn = get_db()
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='monitor_log'"
        )
        has_monitor = cur.fetchone() is not None

        if has_monitor:
            cur = conn.execute(
                "SELECT date, source, count, status, message, created_at "
                "FROM monitor_log WHERE date >= ? ORDER BY date DESC, source",
                ((datetime.now(timezone.utc) + timedelta(hours=8) - timedelta(days=days)).strftime("%Y-%m-%d"),),
            )
            rows = cur.fetchall()
            data = rows_to_list(rows)

            by_source: Dict[str, List[Dict]] = defaultdict(list)
            for d in data:
                by_source[d["source"]].append(d)

            summary = []
            for src, entries in by_source.items():
                ok_days = sum(1 for e in entries if e["status"] == "ok")
                warn_days = sum(1 for e in entries if e["status"] == "warn")
                err_days = sum(1 for e in entries if e["status"] == "error")
                summary.append({
                    "source": src,
                    "total_days": len(entries),
                    "ok_days": ok_days,
                    "warn_days": warn_days,
                    "error_days": err_days,
                    "healthy": err_days == 0,
                })

            return json_response({
                "days": days,
                "has_monitor_log": True,
                "summary": summary,
                "details": data,
            })
        else:
            tables = ["schools", "admission", "forum", "jobs", "control_lines"]
            stats = []
            for t in tables:
                try:
                    cnt_cur = conn.execute(f"SELECT COUNT(*) FROM {t}")
                    cnt = cnt_cur.fetchone()[0]
                    stats.append({"table": t, "count": cnt, "status": "ok" if cnt > 0 else "warn"})
                except Exception:
                    stats.append({"table": t, "count": 0, "status": "error"})

            return json_response({
                "days": days,
                "has_monitor_log": False,
                "message": "monitor_log 表不存在，显示各表记录数作为健康概览",
                "table_stats": stats,
            })
    except Exception as e:
        logger.error(f"monitor_data_health 异常: {e}")
        return json_response({"error": "查询失败"}, 500)


# ---------------------------------------------------------------------------
# 13. GET /api/stats
# ---------------------------------------------------------------------------

@app.get("/api/stats")
def stats():
    """各表记录数统计。"""
    conn = get_db()
    try:
        tables = {
            "schools": "学校",
            "admission": "录取数据",
            "forum": "论坛口碑",
            "jobs": "薪资数据",
            "control_lines": "省控线",
        }
        result: Dict[str, Any] = {}
        for table, label in tables.items():
            try:
                cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                result[table] = {"label": label, "count": count}

                if table == "admission":
                    cur = conn.execute("SELECT COUNT(DISTINCT province) FROM admission")
                    result[table]["provinces"] = cur.fetchone()[0]
                    cur = conn.execute("SELECT MIN(year), MAX(year) FROM admission")
                    row = cur.fetchone()
                    result[table]["year_range"] = f"{row[0]}-{row[1]}" if row[0] else "无"
                elif table == "schools":
                    cur = conn.execute("SELECT COUNT(DISTINCT location) FROM schools")
                    result[table]["locations"] = cur.fetchone()[0]
                elif table == "jobs":
                    cur = conn.execute("SELECT COUNT(DISTINCT city) FROM jobs")
                    result[table]["cities"] = cur.fetchone()[0]
            except Exception:
                result[table] = {"label": label, "count": 0, "error": True}

        return json_response({"stats": result})
    except Exception as e:
        logger.error(f"stats 异常: {e}")
        return json_response({"error": "查询失败", "stats": {}}, 500)


# ---------------------------------------------------------------------------
# 14. GET / → 302 重定向到 /static/index.html
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    """根路径重定向到首页。"""
    return RedirectResponse(url="/static/index.html", status_code=302)


# ---------------------------------------------------------------------------
# 15. GET /api/health — 健康检查
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health_check():
    """健康检查端点（用于监控/负载均衡）。"""
    try:
        conn = get_db()
        conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False

    return json_response({
        "status": "ok" if db_ok else "degraded",
        "version": "2.0.0",
        "database": str(DB_PATH.name) if DB_PATH.exists() else "not_found",
        "deepseek_configured": bool(DEEPSEEK_API_KEY),
    })


# ---------------------------------------------------------------------------
# 静态文件挂载（必须在最后）
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


# ---------------------------------------------------------------------------
# 启动入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    print("=" * 50)
    print("  驷马报考 API Server")
    print(f"  版本: 2.0.0")
    print(f"  数据库: {DB_PATH}")
    print(f"  Key 已配置: {'是' if DEEPSEEK_API_KEY else '否（AI 将降级）'}")
    print(f"  监听: http://{HOST}:{PORT}")
    print(f"  Reload: {RELOAD}")
    print("=" * 50)

    uvicorn.run(
        "app:app",
        host=HOST,
        port=PORT,
        reload=RELOAD,
        log_level=LOG_LEVEL,
    )
