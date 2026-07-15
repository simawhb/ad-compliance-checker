#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
daily_run.py --- 驷马报考 每日采集执行入口

用法:
    python daily_run.py                  # 全量每日运行
    python daily_run.py --dry-run        # 只检查，不实际采集
    python daily_run.py --forum-only     # 只跑论坛巡检
    python daily_run.py --job-only       # 只跑招聘数据
    python daily_run.py --check-only     # 只做网站巡检

执行顺序:
    1. 网站巡检（改版检测）
    2. 论坛舆情巡检
    3. 招聘数据采集
    4. 数据清洗 + 校验
    5. 生成当日简报
    6. 数据采集健康监控
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("daily-run")

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
CONFIG_PATH: Path = PROJECT_ROOT / "config" / "crawl_tasks.json"
REPORTS_DIR: Path = PROJECT_ROOT / "reports" / "daily"

# HTTP 请求超时（秒）
HTTP_TIMEOUT: int = 15
# User-Agent（避免被目标站点拒绝）
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


# ============================================================================
# 配置读取
# ============================================================================


def load_tasks_config() -> Dict[str, Any]:
    """从 JSON 配置文件加载任务列表。

    Returns:
        配置字典；若文件不存在则返回空任务列表。
    """
    if not CONFIG_PATH.exists():
        logger.warning("配置文件不存在: %s，将使用空任务列表", CONFIG_PATH)
        return {"tasks": []}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# Step 1: 网站巡检
# ============================================================================


def check_url(url: str, timeout: int = HTTP_TIMEOUT) -> Tuple[bool, str, float]:
    """检查单个 URL 的可访问性。

    发送 HEAD 请求（降级到 GET），记录响应状态。

    Returns:
        (ok, status_text, elapsed_seconds) 三元组。
        ok=True 表示可正常访问（HTTP 2xx/3xx）。
    """
    start: float = time.monotonic()

    req = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": USER_AGENT},
    )

    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        elapsed: float = time.monotonic() - start
        status_code: int = resp.getcode()
        if 200 <= status_code < 400:
            return True, f"HTTP {status_code}", elapsed
        else:
            return False, f"HTTP {status_code}", elapsed

    except urllib.error.HTTPError as exc:
        elapsed = time.monotonic() - start
        return False, f"HTTP {exc.code}", elapsed
    except urllib.error.URLError as exc:
        elapsed = time.monotonic() - start
        reason: str = str(exc.reason) if exc.reason else "未知错误"
        return False, f"连接失败: {reason}", elapsed
    except Exception as exc:
        elapsed = time.monotonic() - start
        return False, f"异常: {exc}", elapsed


def site_check(dry_run: bool = False) -> List[Dict[str, Any]]:
    """检测已配置任务的 URL 是否仍然可访问。

    Args:
        dry_run: 是否为干运行模式。

    Returns:
        巡检结果列表。
    """
    logger.info("[1/5] 网站改版检测...")
    config: Dict[str, Any] = load_tasks_config()
    tasks: List[Dict[str, Any]] = config.get("tasks", [])

    targets: List[Dict[str, Any]] = [
        t for t in tasks
        if t.get("enabled", True) and t.get("target_url")
    ]

    if not targets:
        logger.info("  （无目标 URL 需要巡检）")
        return []

    logger.info("  共 %d 个目标 URL 待巡检", len(targets))

    results: List[Dict[str, Any]] = []

    for i, task in enumerate(targets, 1):
        url: str = task["target_url"]
        name: str = task["task_name"]
        logger.info("  [%d/%d] 检测: %s → %s", i, len(targets), name, url)

        ok, status_text, elapsed = check_url(url)
        elapsed_ms: int = int(elapsed * 1000)

        result: Dict[str, Any] = {
            "task_name": name,
            "url": url,
            "ok": ok,
            "status_text": status_text,
            "elapsed_ms": elapsed_ms,
        }
        results.append(result)

        status_icon: str = "✓" if ok else "✗"
        logger.info("       %s %s (%dms)", status_icon, status_text, elapsed_ms)

    ok_count: int = sum(1 for r in results if r["ok"])
    fail_count: int = len(results) - ok_count
    logger.info("  巡检完成: %d 正常, %d 异常", ok_count, fail_count)

    return results


# ============================================================================
# Step 2: 论坛舆情巡检
# ============================================================================


def forum_patrol(dry_run: bool = False) -> List[Dict[str, Any]]:
    """论坛舆情巡检——B站（主力）+ 贴吧（备用）"""
    logger.info("[2/6] 论坛舆情巡检...")
    results: List[Dict[str, Any]] = []

    # B站巡检（主力数据源）
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src" / "crawler"))
        from gaokao_spiders.spiders.forum.bilibili_forum_patrol import BilibiliForumPatrol

        extended_keywords = [
            "高考志愿 填报 推荐",
            "大学专业 值得报吗",
            "高考 选专业 避坑",
            "志愿填报 经验分享",
            "大学生活 真实体验 大学",
            "计算机专业 就业",
            "医学专业 报考",
            "法学专业 前景",
            "师范专业 怎么样",
            "高考 院校选择",
            "XX大学 就读体验",
            "考研 选专业",
            "张雪峰 高考志愿",
            "大学排名 2026",
        ]
        patrol = BilibiliForumPatrol(keywords=extended_keywords)
        posts = patrol.run(dry_run=dry_run)
        if not dry_run and posts:
            patrol.save(posts)
        results.append({"platform": "B站", "count": len(posts)})
        logger.info("  B站: %d 条", len(posts))
    except Exception as e:
        logger.warning("B站巡检异常: %s", e)
        results.append({"platform": "B站", "count": 0, "error": str(e)})

    # B站评论深度采集
    try:
        from gaokao_spiders.spiders.forum.bilibili_comments_deep import BilibiliCommentCollector

        collector = BilibiliCommentCollector(max_videos=5)
        comments = collector.run(dry_run=dry_run)
        if not dry_run and comments:
            collector.save(comments)
        results.append({"platform": "B站评论", "count": len(comments)})
        logger.info("  B站评论: %d 条", len(comments))
    except Exception as e:
        logger.warning("B站评论采集异常: %s", e)
        results.append({"platform": "B站评论", "count": 0, "error": str(e)})

    return results


# ============================================================================
# Step 3: 招聘数据采集
# ============================================================================


def job_data(dry_run: bool = False) -> List[Dict[str, Any]]:
    """招聘数据采集——智联招聘（Playwright浏览器版）"""
    logger.info("[3/6] 招聘数据采集...")
    results: List[Dict[str, Any]] = []

    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src" / "crawler"))
        from gaokao_spiders.spiders.employment.job_collector_final import JobCollectorFinal
        collector = JobCollectorFinal(quick=True)
        stats = collector.run(dry_run=dry_run)
        if not dry_run and stats:
            collector.save(stats)
        results.append({"platform": "智联招聘", "count": len(stats)})
        total = sum(s.total_job_count for s in stats)
        logger.info("  智联招聘: %d 条统计, %d 个岗位样本", len(stats), total)
    except Exception as e:
        logger.warning("智联采集异常: %s", e)
        results.append({"platform": "智联招聘", "count": 0, "error": str(e)})

    return results


# ============================================================================
# Step 4: 数据清洗与校验
# ============================================================================


def clean_and_validate(dry_run: bool = False) -> Dict[str, Any]:
    """清洗+校验当日采集数据。

    Args:
        dry_run: 是否为干运行模式。

    Returns:
        校验摘要字典。
    """
    logger.info("[4/6] 数据清洗与校验...")

    if dry_run:
        logger.info("  (DRY RUN — 仅打印，不执行)")
        return {"passed": 0, "failed": 0, "total": 0}

    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src" / "etl"))
        from data_validator import validate_batch
    except ImportError as e:
        logger.error("无法导入 data_validator: %s", e)
        return {"passed": 0, "failed": 0, "total": 0, "error": str(e)}

    today_str: str = datetime.now().strftime("%Y-%m-%d")
    base: Path = PROJECT_ROOT

    data_sources: List[Dict[str, Any]] = [
        {
            "path": base / "data" / "raw" / "forum" / "bilibili" / f"{today_str}.jsonl",
            "table": "user_reviews",
            "label": "B站论坛",
        },
        {
            "path": base / "data" / "raw" / "employment" / "jobs" / f"zhaopin_{today_str}.jsonl",
            "table": "employment",
            "label": "智联招聘",
        },
    ]

    all_details: List[Dict[str, Any]] = []
    total_passed: int = 0
    total_failed: int = 0
    total_rows: int = 0

    for src in data_sources:
        file_path: Path = src["path"]
        if not file_path.exists():
            logger.info("  %s: 无当日数据文件 (%s)", src['label'], file_path.name)
            continue

        try:
            records: List[dict] = []
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))

            if not records:
                logger.info("  %s: 文件存在但内容为空", src['label'])
                continue

            result: Dict[str, Any] = validate_batch(records, src["table"])
            if "error" in result:
                logger.warning("  %s: 校验失败 — %s", src['label'], result['error'])
                continue

            all_details.append({"source": src["label"], "table": src["table"], **result})
            total_passed += result["passed"]
            total_failed += result["failed"]
            total_rows += result["total"]
            logger.info(
                "  %s: %d 条, 通过 %d, 失败 %d (%s%%)",
                src['label'], result['total'],
                result['passed'], result['failed'],
                result['pass_rate'],
            )

        except Exception as e:
            logger.warning("  %s: 校验异常 — %s", src['label'], e)

    summary: Dict[str, Any] = {
        "passed": total_passed,
        "failed": total_failed,
        "total": total_rows,
        "details": all_details,
    }
    logger.info("")
    return summary


# ============================================================================
# Step 5: 生成当日简报
# ============================================================================


def generate_daily_report(
    site_results: List[Dict[str, Any]],
    forum_results: List[Dict[str, Any]],
    job_results: List[Dict[str, Any]],
    validation_summary: Dict[str, Any],
    dry_run: bool = False,
) -> Optional[Path]:
    """生成当日简报 Markdown 文件。

    Args:
        site_results: 网站巡检结果列表。
        forum_results: 论坛巡检结果列表。
        job_results: 招聘采集结果列表。
        validation_summary: 数据校验摘要。
        dry_run: 是否为干运行模式。

    Returns:
        简报文件路径；dry_run 模式下返回 None。
    """
    logger.info("[5/5] 生成当日简报...")

    today_str: str = datetime.now().strftime("%Y-%m-%d")
    now_str: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    site_ok: int = sum(1 for r in site_results if r["ok"])
    site_total: int = len(site_results)

    lines: List[str] = []

    lines.append(f"# 驷马报考 每日简报")
    lines.append(f"")
    lines.append(f"> 自动生成于：{now_str}")
    lines.append(f"")

    # 采集概况
    lines.append(f"## 采集概况")
    lines.append(f"")
    lines.append(f"| 项目 | 状态 | 新增数据量 | 备注 |")
    lines.append(f"|------|------|-----------|------|")

    lines.append(
        f"| 网站巡检 | {'✓' if site_ok == site_total else '⚠'} | — | "
        f"{site_ok}/{site_total} 正常 |"
    )

    for fr in forum_results:
        platform = fr["platform"]
        count = fr["count"]
        error = fr.get("error")
        status = "⚠" if error else "✓"
        lines.append(f"| 论坛巡检-{platform} | {status} | {count} 条 | {'正常' if not error else error[:30]} |")

    for jr in job_results:
        platform = jr["platform"]
        count = jr["count"]
        error = jr.get("error")
        status = "⚠" if error else "✓"
        lines.append(f"| {platform} | {status} | {count} 条 | {'正常' if not error else error[:30]} |")

    val_status: str = "✓" if validation_summary.get("failed", 0) == 0 else "⚠"
    lines.append(
        f"| 数据校验 | {val_status} | "
        f"通过 {validation_summary.get('passed', 0)} 条 | — |"
    )
    lines.append(f"")

    # 网站巡检详情
    lines.append(f"## 网站巡检结果")
    lines.append(f"")
    lines.append(f"| 目标 | 状态 | 耗时(ms) | 备注 |")
    lines.append(f"|------|------|----------|------|")

    for r in site_results:
        ok_mark: str = "✓ OK" if r["ok"] else "✗ 异常"
        lines.append(
            f"| {r['task_name']} | {ok_mark} | "
            f"{r['elapsed_ms']} | {r['status_text']} |"
        )
    lines.append(f"")

    # 异常数据
    lines.append(f"## 异常数据 / 待处理")
    lines.append(f"")

    failed_sites: List[Dict[str, Any]] = [
        r for r in site_results if not r["ok"]
    ]
    if failed_sites:
        for i, r in enumerate(failed_sites, 1):
            lines.append(
                f"{i}. [{r['task_name']}] {r['url']} "
                f"— {r['status_text']}"
            )
    else:
        lines.append("1. 无异常")
    lines.append(f"")

    # 数据质量
    lines.append(f"## 数据质量")
    lines.append(f"")
    if validation_summary.get("total", 0) > 0:
        pass_rate: float = (
            validation_summary["passed"] / validation_summary["total"] * 100
            if validation_summary.get("total", 0) > 0
            else 100.0
        )
        lines.append(f"- 总通过率：{pass_rate:.1f}%")
    else:
        lines.append(f"- 今日无新采集数据")
    lines.append(f"")
    if site_total > 0:
        lines.append(f"- 网站可访问率：{site_ok}/{site_total} ({site_ok / site_total * 100:.0f}%)")
    lines.append(f"")

    # 明日计划
    lines.append(f"## 明日计划")
    lines.append(f"")
    if failed_sites:
        lines.append(f"- 跟进异常网站: {', '.join(r['task_name'] for r in failed_sites)}")
    lines.append(f"- 按频率检查是否有待执行的定期采集任务")
    if dry_run:
        lines.append(f"- (DRY RUN 模式，本次未执行实际采集)")
    lines.append(f"")

    report_text: str = "\n".join(lines)

    if dry_run:
        logger.info("  [DRY RUN] 简报预览：\n%s", report_text)
        return None

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path: Path = REPORTS_DIR / f"{today_str}_report.md"
    report_path.write_text(report_text, encoding="utf-8")
    logger.info("  简报已保存: %s", report_path)
    return report_path


# ============================================================================
# 主入口
# ============================================================================


def main() -> None:
    """命令行入口 —— 根据参数选择性执行每日流水线。"""
    parser = argparse.ArgumentParser(
        description="驷马报考·每日采集流水线",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只检查，不实际采集（打印预览不写文件）",
    )
    parser.add_argument(
        "--forum-only", action="store_true",
        help="只做论坛巡检",
    )
    parser.add_argument(
        "--job-only", action="store_true",
        help="只做招聘数据",
    )
    parser.add_argument(
        "--check-only", action="store_true",
        help="只做网站巡检",
    )
    args = parser.parse_args()

    logger.info("=== 驷马报考 每日采集流水线 ===")
    logger.info("日期: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    if args.dry_run:
        logger.info("模式: DRY RUN（只检查，不执行实际采集）")

    if args.dry_run:
        site_results = site_check(dry_run=True)
        forum_results = forum_patrol(dry_run=True)
        job_results = job_data(dry_run=True)
        generate_daily_report(
            site_results, forum_results, job_results,
            {"passed": 0, "failed": 0, "total": 0},
            dry_run=True,
        )
        logger.info("=== DRY RUN 完成 ===")
        return

    # 单项模式
    if args.forum_only:
        forum_patrol(dry_run=False)
        return
    if args.job_only:
        job_data(dry_run=False)
        return
    if args.check_only:
        site_results = site_check(dry_run=False)
        generate_daily_report(
            site_results, [], [],
            {"passed": 0, "failed": 0, "total": 0},
            dry_run=False,
        )
        return

    # 全量运行
    site_results = site_check(dry_run=False)
    forum_results = forum_patrol(dry_run=False)
    job_results = job_data(dry_run=False)
    validation_summary = clean_and_validate(dry_run=False)
    generate_daily_report(
        site_results, forum_results, job_results,
        validation_summary,
        dry_run=False,
    )

    # Step 6: 数据采集监控
    try:
        logger.info("[6/6] 数据采集健康监控...")
        from src.scripts.monitor_data import run_monitor
        _, _, monitor_report = run_monitor(write_db=True)
        logger.info("")
        logger.info(monitor_report)
    except Exception as e:
        logger.warning("监控模块执行异常: %s", e)
        import traceback
        traceback.print_exc()

    logger.info("=== 每日采集完成 ===")


if __name__ == "__main__":
    main()
