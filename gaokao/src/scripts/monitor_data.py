#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
monitor_data.py --- 数据采集管线监控与异常告警

功能：
  1. 统计 data/raw/forum/bilibili/ 下最近7天的jsonl文件，按数据源统计每日条数
  2. 统计 data/raw/employment/jobs/ 下最近7天的jsonl文件，按数据源统计每日条数
  3. 如果某天条数 < 过去7天平均值的30%，标记为"异常"
  4. 输出监控报告
  5. 将监控结果写入 gaokao.db 的 monitor_log 表
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

# 数据目录
def _resolve_data_dir(subpath: str) -> Path:
    """解析数据目录路径"""
    return PROJECT_ROOT / "data" / "raw" / subpath

FORUM_DIR: Path = _resolve_data_dir("forum/bilibili")
JOBS_DIR: Path = _resolve_data_dir("employment/jobs")
DB_PATH: Path = PROJECT_ROOT / "data" / "simadb" / "gaokao.db"

# 数据源配置：名称 → (目录路径, 文件匹配模式, 类型标签)
DATA_SOURCES: Dict[str, Dict[str, Any]] = {
    "bilibili_forum": {
        "dir": FORUM_DIR,
        "label": "B站论坛巡检",
        "file_pattern": lambda fname: fname.endswith(".jsonl") and not fname.startswith("comments_") and not fname.startswith("."),
        "extract_date": lambda fname: fname.replace(".jsonl", ""),
    },
    "bilibili_comment": {
        "dir": FORUM_DIR,
        "label": "B站评论深度采集",
        "file_pattern": lambda fname: fname.startswith("comments_") and fname.endswith(".jsonl"),
        "extract_date": lambda fname: fname.replace("comments_", "").replace(".jsonl", ""),
    },
    "zhaopin": {
        "dir": JOBS_DIR,
        "label": "智联招聘采集",
        "file_pattern": lambda fname: fname.startswith("zhaopin_") and fname.endswith(".jsonl"),
        "extract_date": lambda fname: fname.replace("zhaopin_", "").replace(".jsonl", ""),
    },
}

# 当前日期（北京时间，UTC+8）
def _today_cn() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d")


# ============================================================================
# 数据读取与统计
# ============================================================================


def count_jsonl_lines(path: Path) -> int:
    """统计 jsonl 文件的行数（即记录数）"""
    if not path.exists() or path.stat().st_size == 0:
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def scan_data_source(
    source_key: str,
    config: Dict[str, Any],
    days: int = 7,
) -> List[Dict[str, Any]]:
    """扫描某个数据源目录，返回最近 N 天的每日统计。

    Args:
        source_key: 数据源键名。
        config: 数据源配置。
        days: 统计最近多少天（默认7天）。

    Returns:
        每日统计列表，每项 {date, count}。
    """
    data_dir: Path = config["dir"]
    file_filter = config["file_pattern"]
    extract_date = config["extract_date"]

    if not data_dir.exists():
        return []

    today = datetime.now(timezone.utc) + timedelta(hours=8)
    results: List[Dict[str, Any]] = []

    for i in range(days - 1, -1, -1):
        target_date = today - timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")

        count = 0
        for fpath in data_dir.iterdir():
            if not fpath.is_file() or not file_filter(fpath.name):
                continue
            file_date = extract_date(fpath.name)
            if file_date == date_str:
                count += count_jsonl_lines(fpath)

        results.append({"date": date_str, "count": count})

    return results


def scan_all_sources(days: int = 7) -> Dict[str, List[Dict[str, Any]]]:
    """扫描所有数据源，返回每日统计。

    Returns:
        {source_key: [{date, count}, ...]}
    """
    result: Dict[str, List[Dict[str, Any]]] = {}
    for key, config in DATA_SOURCES.items():
        result[key] = scan_data_source(key, config, days=days)
    return result


# ============================================================================
# 异常检测
# ============================================================================


def detect_anomaly(
    daily_data: List[Dict[str, Any]],
    threshold_ratio: float = 0.3,
) -> List[Dict[str, Any]]:
    """检测每日数据量是否异常。

    算法：
      1. 计算过去 N 天中 count>0 的天的平均值（排除 count=0 的异常天本身）。
      2. 如果某天 count < 平均值 * threshold_ratio，标记为异常。
      3. 如果连续 count=0，额外标记。

    Args:
        daily_data: [{date, count}, ...]
        threshold_ratio: 异常阈值比例（默认30%）。

    Returns:
        添加了异常标记的结果列表，每项新增：
          - status: "ok" | "warn" | "error"
          - message: 异常原因描述
    """
    # 计算正常天的平均值（排除 count=0 的天）
    non_zero_counts = [d["count"] for d in daily_data if d["count"] > 0]
    avg_count = sum(non_zero_counts) / len(non_zero_counts) if non_zero_counts else 0

    results: List[Dict[str, Any]] = []
    zero_streak = 0

    for d in daily_data:
        entry: Dict[str, Any] = {
            "date": d["date"],
            "count": d["count"],
            "status": "ok",
            "message": "",
        }

        if d["count"] == 0:
            zero_streak += 1
            if zero_streak >= 3:
                entry["status"] = "warn"
                entry["message"] = f"连续{zero_streak}天数据量为0，可能数据源已改版"
            elif zero_streak >= 1:
                entry["status"] = "warn"
                entry["message"] = f"当日数据量为0（连续第{zero_streak}天）"
        else:
            zero_streak = 0
            if avg_count > 0 and d["count"] < avg_count * threshold_ratio:
                entry["status"] = "error"
                entry["message"] = (
                    f"数据量异常：当日 {d['count']} 条，"
                    f"低于近7天均值 {avg_count:.1f} 的 {threshold_ratio*100:.0f}%"
                    f"（阈值 {avg_count * threshold_ratio:.1f} 条）"
                )

        results.append(entry)

    return results


# ============================================================================
# 数据库监控日志
# ============================================================================


def init_monitor_table(db_path: Path = DB_PATH) -> None:
    """创建 monitor_log 表（如果不存在）"""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS monitor_log (
                date TEXT,
                source TEXT,
                count INT,
                status TEXT,
                message TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_monitor_log_date ON monitor_log(date)"
        )
        conn.commit()
    finally:
        conn.close()


def write_monitor_log(
    source_key: str,
    source_label: str,
    daily_results: List[Dict[str, Any]],
    db_path: Path = DB_PATH,
) -> None:
    """将监控结果写入 monitor_log 表。

    每条记录包含日期、数据源、条数、状态、消息、创建时间。
    """
    conn = sqlite3.connect(str(db_path))
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        for entry in daily_results:
            conn.execute(
                """
                INSERT INTO monitor_log (date, source, count, status, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry["date"],
                    source_label,
                    entry["count"],
                    entry["status"],
                    entry["message"],
                    now_str,
                ),
            )
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# 报告生成
# ============================================================================


def generate_report(
    all_data: Dict[str, List[Dict[str, Any]]],
    anomalies: Dict[str, List[Dict[str, Any]]],
) -> str:
    """生成人类可读的监控报告。

    Args:
        all_data: 所有数据源的原始统计。
        anomalies: 所有数据源的异常检测结果。

    Returns:
        格式化的 Markdown 报告文本。
    """
    lines: List[str] = []
    today = _today_cn()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append(f"## 数据采集健康监控")
    lines.append(f"")
    lines.append(f"> 自动检测于：{now_str}")
    lines.append(f"")

    has_issue = False

    for source_key, config in DATA_SOURCES.items():
        label = config["label"]
        daily_data = all_data.get(source_key, [])
        anomaly_data = anomalies.get(source_key, [])

        if not daily_data:
            lines.append(f"### {label}")
            lines.append(f"")
            lines.append(f"⚠️ 无数据文件（目录不存在或为空）")
            lines.append(f"")
            continue

        lines.append(f"### {label}")
        lines.append(f"")
        lines.append(f"| 日期 | 数据量 | 状态 |")
        lines.append(f"|------|--------|------|")

        for entry in anomaly_data:
            status_icon = "✅" if entry["status"] == "ok" else ("⚠️" if entry["status"] == "warn" else "❌")
            status_text = f"{status_icon} {entry['status'].upper()}"
            if entry["message"]:
                status_text += f" — {entry['message']}"
            lines.append(f"| {entry['date']} | {entry['count']} | {status_text} |")

        # 检查是否有异常
        source_issues = [e for e in anomaly_data if e["status"] != "ok"]
        if source_issues:
            has_issue = True
        lines.append(f"")

    # 汇总
    lines.append(f"### 汇总")
    lines.append(f"")
    if has_issue:
        lines.append(f"⚠️ 存在数据异常，请关注上表标记项。")
    else:
        lines.append(f"✅ 所有数据源近7天采集正常。")

    # 告警提醒
    lines.append(f"")
    lines.append(f"告警规则：")
    lines.append(f"- 某天条数低于近7天均值30% → 标记异常")
    lines.append(f"- 连续3天条数为0 → 标记警告（可能数据源改版）")

    return "\n".join(lines)


# ============================================================================
# 主入口
# ============================================================================


def run_monitor(
    days: int = 7,
    write_db: bool = True,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, str], str]:
    """执行一次完整的监控流程。

    Args:
        days: 统计最近多少天（默认7天）。
        write_db: 是否将结果写入数据库（默认True）。

    Returns:
        (all_data, anomalies_dict, report_text) 三元组。
        - all_data: {source_key: [{date, count}, ...]}
        - anomalies_dict: {source_key: report_text}
        - report_text: 完整的 Markdown 报告
    """
    all_data = scan_all_sources(days=days)

    anomalies: Dict[str, List[Dict[str, Any]]] = {}
    for source_key, daily_data in all_data.items():
        anomalies[source_key] = detect_anomaly(daily_data)

    # 写入数据库
    if write_db:
        init_monitor_table()
        for source_key in DATA_SOURCES:
            if source_key in anomalies:
                write_monitor_log(source_key, DATA_SOURCES[source_key]["label"], anomalies[source_key])

    report_text = generate_report(all_data, anomalies)
    return all_data, anomalies, report_text


def main() -> None:
    """CLI 入口"""
    print("=== 数据采集管线监控 ===")
    print()

    all_data, anomalies, report = run_monitor()
    print(report)

    # 如果有异常，非零退出
    has_error = any(
        entry["status"] == "error"
        for source_anomalies in anomalies.values()
        for entry in source_anomalies
    )
    if has_error:
        print("\n⚠️ 发现数据异常，请及时排查！")
        sys.exit(1)


if __name__ == "__main__":
    main()
