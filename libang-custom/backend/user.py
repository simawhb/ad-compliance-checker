# -*- coding: utf-8 -*-
"""
力邦营养企业定制版 - 用户管理（企业内用版 · 无配额限制）
所有用户默认无限额度，无需升级/付费
"""
import os
import json
import time
import hashlib
import sqlite3
import logging
import threading

logger = logging.getLogger(__name__)

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "libang_checker.db")

_local = threading.local()

PLANS = {
    "enterprise": {"name": "企业版", "quick": 999999, "deep": 999999},
    "free": {"name": "免费版", "quick": 999999, "deep": 999999},
    "pro": {"name": "专业版", "quick": 999999, "deep": 999999},
}


def _get_db():
    """线程本地连接"""
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(DB_DIR, exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA busy_timeout=5000")
    return _local.conn


def init():
    """初始化数据库（企业内用版）"""
    db = _get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            openid TEXT PRIMARY KEY,
            plan TEXT DEFAULT 'enterprise',
            quick_used INTEGER DEFAULT 0,
            deep_used INTEGER DEFAULT 0,
            use_date TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS check_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            openid TEXT NOT NULL,
            text TEXT NOT NULL,
            industry TEXT DEFAULT '',
            check_type TEXT DEFAULT 'quick',
            result TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS upgrade_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_hash TEXT UNIQUE NOT NULL,
            plan TEXT NOT NULL,
            used_by TEXT DEFAULT '',
            used_at TEXT DEFAULT '',
            revoked INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_history_openid ON check_history(openid);
        CREATE INDEX IF NOT EXISTS idx_history_created ON check_history(created_at);
    """)
    db.commit()
    logger.info(f"力邦营养企业版数据库已就绪: {DB_PATH}")


def _ensure_user(openid):
    """确保用户存在（自动注册企业版）"""
    db = _get_db()
    cur = db.execute("SELECT openid FROM users WHERE openid=?", (openid,))
    if cur.fetchone() is None:
        today = time.strftime("%Y-%m-%d")
        db.execute(
            "INSERT INTO users (openid, plan, use_date) VALUES (?, 'enterprise', ?)",
            (openid, today),
        )
        db.commit()
        logger.info(f"企业用户自动注册: {openid}")


def get_user(openid):
    """获取用户信息"""
    _ensure_user(openid)
    db = _get_db()
    cur = db.execute("SELECT * FROM users WHERE openid=?", (openid,))
    row = cur.fetchone()
    if not row:
        return {"plan": "enterprise", "quick_quota": 999999, "deep_quota": 999999,
                "quick_used": 0, "deep_used": 0}
    plan = row["plan"]
    plan_info = PLANS.get(plan, PLANS["enterprise"])
    return {
        "plan": plan,
        "plan_name": plan_info["name"],
        "quick_quota": plan_info["quick"],
        "deep_quota": plan_info["deep"],
        "quick_used": row["quick_used"],
        "deep_used": row["deep_used"],
        "use_date": row["use_date"],
    }


def check_quota(openid, deep=False):
    """企业版：永远有配额"""
    _ensure_user(openid)
    return True, "ok"


def record_use(openid, deep=False):
    """记录使用（仅统计，不限制）"""
    try:
        db = _get_db()
        today = time.strftime("%Y-%m-%d")
        if deep:
            db.execute("UPDATE users SET deep_used=deep_used+1, use_date=?, updated_at=datetime('now','localtime') WHERE openid=?",
                       (today, openid))
        else:
            db.execute("UPDATE users SET quick_used=quick_used+1, use_date=?, updated_at=datetime('now','localtime') WHERE openid=?",
                       (today, openid))
        db.commit()
    except Exception as e:
        logger.warning(f"记录使用失败: {e}")


def record_check(openid, text, industry, check_type, result):
    """记录检测历史"""
    try:
        db = _get_db()
        result_json = json.dumps(result, ensure_ascii=False)
        text_preview = text[:200]
        db.execute(
            "INSERT INTO check_history (openid, text, industry, check_type, result) VALUES (?, ?, ?, ?, ?)",
            (openid, text_preview, industry, check_type, result_json),
        )
        db.commit()
    except Exception as e:
        logger.warning(f"记录检测历史失败: {e}")


def get_history(openid, page=1, page_size=20):
    """获取检测历史"""
    db = _get_db()
    offset = (page - 1) * page_size
    rows = db.execute(
        "SELECT id, text, industry, check_type, result, created_at FROM check_history WHERE openid=? ORDER BY id DESC LIMIT ? OFFSET ?",
        (openid, page_size, offset),
    ).fetchall()
    items = [{"id": r["id"], "text": r["text"], "industry": r["industry"],
              "check_type": r["check_type"], "created_at": r["created_at"]} for r in rows]
    total = db.execute("SELECT COUNT(*) FROM check_history WHERE openid=?", (openid,)).fetchone()[0]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_record_detail(record_id, openid):
    db = _get_db()
    row = db.execute(
        "SELECT id, text, industry, check_type, result, created_at FROM check_history WHERE id=? AND openid=?",
        (record_id, openid),
    ).fetchone()
    if not row:
        return None
    return {"id": row["id"], "text": row["text"], "industry": row["industry"],
            "check_type": row["check_type"], "result": row["result"], "created_at": row["created_at"]}


def delete_record(record_id, openid):
    db = _get_db()
    db.execute("DELETE FROM check_history WHERE id=? AND openid=?", (record_id, openid))
    db.commit()
    return True


def clear_history(openid):
    db = _get_db()
    cur = db.execute("DELETE FROM check_history WHERE openid=?", (openid,))
    db.commit()
    return cur.rowcount


def upgrade(openid, plan):
    """企业版中升级实际上只是切换套餐标签"""
    db = _get_db()
    db.execute("UPDATE users SET plan=?, updated_at=datetime('now','localtime') WHERE openid=?", (plan, openid))
    db.commit()


# 以下为管理员接口（保留基础管理功能）
def _get_all_users(page=1, page_size=50):
    db = _get_db()
    offset = (page - 1) * page_size
    rows = db.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?", (page_size, offset)).fetchall()
    items = [dict(r) for r in rows]
    total = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def _get_admin_stats():
    db = _get_db()
    users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    checks = db.execute("SELECT COUNT(*) FROM check_history").fetchone()[0]
    return {"total_users": users, "total_checks": checks}


def _cleanup_old_records(days=90):
    db = _get_db()
    cur = db.execute(
        "DELETE FROM check_history WHERE created_at < datetime('now', 'localtime', ?)",
        (f"-{days} days",),
    )
    db.commit()
    if cur.rowcount > 0:
        logger.info(f"已清理 {cur.rowcount} 条旧记录")


def validate_key(key, openid):
    return False, "企业版无需升级密钥"


def generate_key(plan):
    return ""


def list_keys(page=1, page_size=50):
    return {"items": [], "total": 0}


def get_key_stats():
    return {"total": 0, "used": 0, "available": 0}


def revoke_key(key_id):
    return True
