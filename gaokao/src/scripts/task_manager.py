#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
task_manager.py --- 驷马报考 采集任务管理 CLI

用法:
    python src/scripts/task_manager.py list
    python src/scripts/task_manager.py run <task_name>
    python src/scripts/task_manager.py status
    python src/scripts/task_manager.py add --name xxx --type schools \
        --url xxx --frequency yearly --strategy scrapy

对应数据表:
    meta.crawl_tasks  (设计见 PLAN.md §2.8)

配置文件:
    config/crawl_tasks.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH: Path = PROJECT_ROOT / "config" / "crawl_tasks.json"
CRAWLER_ROOT: Path = PROJECT_ROOT / "src" / "crawler" / "gaokao_spiders" / "spiders"

# 合法的频率与策略枚举
VALID_FREQUENCIES: set[str] = {"once", "daily", "weekly", "yearly"}
VALID_STRATEGIES: set[str] = {"api", "scrapy", "selenium", "script"}
VALID_DATA_TYPES: set[str] = {
    "schools", "majors", "admission", "policy",
    "employment", "ranking", "forum", "meta",
}


# ============================================================================
# 配置读写
# ============================================================================


def load_config() -> Dict[str, Any]:
    """从 JSON 配置文件加载任务列表。

    Returns:
        配置字典，格式为 {"tasks": [...]}。

    Raises:
        SystemExit: 配置文件不存在时退出。
    """
    if not CONFIG_PATH.exists():
        print(f"错误: 配置文件不存在 — {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: Dict[str, Any]) -> None:
    """将任务列表写入 JSON 配置文件。

    Args:
        config: 配置字典。
    """
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"配置已保存: {CONFIG_PATH}")


def find_task(config: Dict[str, Any], task_name: str) -> Optional[Dict[str, Any]]:
    """按名称查找任务。

    Args:
        config: 配置字典。
        task_name: 任务名称。

    Returns:
        任务字典，若未找到返回 None。
    """
    for t in config.get("tasks", []):
        if t.get("task_name") == task_name:
            return t
    return None


# ============================================================================
# 子命令实现
# ============================================================================


def cmd_list(config: Dict[str, Any]) -> None:
    """list — 列出所有已注册的采集任务。"""
    tasks: List[Dict[str, Any]] = config.get("tasks", [])

    if not tasks:
        print("（暂无已注册的采集任务）")
        return

    # 表头
    header = (
        f"{'任务名':<20} {'频率':<8} {'类型':<10} "
        f"{'策略':<10} {'启用':<5} {'目标URL'}"
    )
    print(header)
    print("-" * max(len(header), 80))

    for t in tasks:
        url = t.get("target_url") or "-"
        if len(url) > 40:
            url = url[:37] + "..."
        print(
            f"{t['task_name']:<20} "
            f"{t.get('frequency', '-'):<8} "
            f"{t.get('data_type', '-'):<10} "
            f"{t.get('crawl_strategy', '-'):<10} "
            f"{'✓' if t.get('enabled') else '✗':<5} "
            f"{url}"
        )
    print(f"\n共 {len(tasks)} 个任务")


def cmd_run(config: Dict[str, Any], task_name: str) -> None:
    """run <task_name> — 运行指定的采集任务。

    根据任务配置的 strategy 决定执行方式：
      - scrapy 策略 → 通过 spider 字段找到对应爬虫文件直接运行
      - script 策略 → 执行 script 字段指定的命令
    """
    task = find_task(config, task_name)

    if task is None:
        print(f"错误: 未找到任务 '{task_name}'", file=sys.stderr)
        print("可用任务:", ", ".join(
            t["task_name"] for t in config.get("tasks", [])
        ))
        sys.exit(1)

    if not task.get("enabled", True):
        print(f"警告: 任务 '{task_name}' 已被禁用")

    print(f"执行任务: {task_name} ({task.get('description', '')})")
    print(f"  目标 URL: {task.get('target_url', '-')}")
    print(f"  策略: {task.get('crawl_strategy', '-')}")
    print()

    now_iso: str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- 构建执行命令 ---
    cmd_parts: List[str] = []

    if task.get("crawl_strategy") == "script" and task.get("script"):
        # 直接执行指定的命令（可能是带参数的脚本调用）
        cmd_parts = task["script"].split()
        # 确保使用绝对路径
        if not Path(cmd_parts[0]).is_absolute():
            cmd_parts[0] = str(PROJECT_ROOT / cmd_parts[0])
        cmd_parts = [sys.executable] + cmd_parts

    elif task.get("spider"):
        spider_path = CRAWLER_ROOT / task["spider"]
        if not spider_path.exists():
            # 更新任务状态为失败
            task["last_run_at"] = now_iso
            task["last_status"] = "failed"
            task["last_error"] = f"Spider 文件不存在: {spider_path}"
            save_config(config)
            print(f"错误: Spider 文件不存在 — {spider_path}", file=sys.stderr)
            sys.exit(1)
        cmd_parts = [sys.executable, str(spider_path)]

    elif task.get("crawl_strategy") == "scrapy":
        # 通过 scrapy 命令执行
        cmd_parts = [
            sys.executable, "-m", "scrapy", "crawl", task_name,
        ]

    else:
        print(
            f"错误: 任务 '{task_name}' 没有配置 spider/script 字段，"
            f"无法自动执行",
            file=sys.stderr,
        )
        task["last_run_at"] = now_iso
        task["last_status"] = "failed"
        task["last_error"] = "任务缺少 spider 或 script 配置"
        save_config(config)
        sys.exit(1)

    print(f"命令: {' '.join(cmd_parts)}")
    print("-" * 60)

    # --- 执行 ---
    try:
        if task.get("crawl_strategy") == "scrapy" and not task.get("spider"):
            # Scrapy crawl 需要在项目目录执行
            result = subprocess.run(
                cmd_parts,
                cwd=str(PROJECT_ROOT / "src" / "crawler"),
                capture_output=False,
                text=True,
            )
        else:
            result = subprocess.run(
                cmd_parts,
                cwd=str(PROJECT_ROOT),
                capture_output=False,
                text=True,
            )
    except FileNotFoundError as exc:
        task["last_run_at"] = now_iso
        task["last_status"] = "failed"
        task["last_error"] = f"执行失败: {exc}"
        save_config(config)
        print(f"错误: 无法执行 — {exc}", file=sys.stderr)
        sys.exit(1)

    # --- 更新任务状态 ---
    task["last_run_at"] = now_iso
    if result.returncode == 0:
        task["last_status"] = "success"
        task["last_error"] = None
        print(f"\n✓ 任务 '{task_name}' 执行成功")
    else:
        task["last_status"] = "failed"
        task["last_error"] = f"退出码: {result.returncode}"
        print(f"\n✗ 任务 '{task_name}' 执行失败 (退出码: {result.returncode})")

    save_config(config)


def cmd_status(config: Dict[str, Any]) -> None:
    """status — 查看所有任务的运行状态。"""
    tasks: List[Dict[str, Any]] = config.get("tasks", [])

    if not tasks:
        print("（暂无已注册的采集任务）")
        return

    header = (
        f"{'任务名':<20} {'频率':<8} {'上次状态':<10} "
        f"{'上次运行时间':<22} {'错误信息'}"
    )
    print(header)
    print("-" * max(len(header), 100))

    for t in tasks:
        last_status = t.get("last_status") or "-"
        last_run = t.get("last_run_at") or "-"
        error = t.get("last_error") or "-"
        if len(error) > 35:
            error = error[:32] + "..."

        # 状态着色标记
        status_mark = last_status
        if last_status == "success":
            status_mark = "✓ success"
        elif last_status == "failed":
            status_mark = "✗ failed"
        elif last_status == "partial":
            status_mark = "⚠ partial"
        else:
            status_mark = "○ pending"

        print(
            f"{t['task_name']:<20} "
            f"{t.get('frequency', '-'):<8} "
            f"{status_mark:<10} "
            f"{last_run:<22} "
            f"{error}"
        )

    print(f"\n共 {len(tasks)} 个任务")


def cmd_add(config: Dict[str, Any], args: argparse.Namespace) -> None:
    """add — 注册一个新的采集任务。

    Args:
        config: 当前配置字典。
        args: 解析后的命令行参数。
    """
    # --- 参数校验 ---
    task_name: str = args.name.strip()

    if not task_name:
        print("错误: --name 不能为空", file=sys.stderr)
        sys.exit(1)

    if find_task(config, task_name) is not None:
        print(f"错误: 任务 '{task_name}' 已存在", file=sys.stderr)
        sys.exit(1)

    frequency: str = args.frequency or "yearly"
    if frequency not in VALID_FREQUENCIES:
        print(
            f"错误: 无效的频率 '{frequency}'，"
            f"可选: {', '.join(sorted(VALID_FREQUENCIES))}",
            file=sys.stderr,
        )
        sys.exit(1)

    strategy: str = args.strategy or "scrapy"
    if strategy not in VALID_STRATEGIES:
        print(
            f"错误: 无效的策略 '{strategy}'，"
            f"可选: {', '.join(sorted(VALID_STRATEGIES))}",
            file=sys.stderr,
        )
        sys.exit(1)

    data_type: str = args.type or "meta"
    if data_type not in VALID_DATA_TYPES:
        print(
            f"警告: 未知的数据类型 '{data_type}'，"
            f"已知: {', '.join(sorted(VALID_DATA_TYPES))}",
        )

    url: str = args.url or ""

    spider: Optional[str] = args.spider if hasattr(args, "spider") and args.spider else None
    description: str = args.description or task_name

    # --- 构建任务 ---
    new_task: Dict[str, Any] = {
        "task_name": task_name,
        "description": description,
        "target_url": url if url else None,
        "data_type": data_type,
        "crawl_strategy": strategy,
        "frequency": frequency,
        "enabled": True,
        "spider": spider,
        "script": None,
        "last_run_at": None,
        "last_status": None,
        "last_error": None,
        "next_run_at": None,
    }

    config.setdefault("tasks", []).append(new_task)
    save_config(config)
    print(f"✓ 任务 '{task_name}' 已注册")


# ============================================================================
# CLI 入口
# ============================================================================


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="task_manager",
        description="驷马报考 — 采集任务管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s list                           列出所有任务
  %(prog)s run moe_schools                运行指定任务
  %(prog)s status                         查看任务运行状态
  %(prog)s add --name my_task --type schools \\
      --url https://example.com --frequency yearly --strategy scrapy
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ---- list ----
    subparsers.add_parser("list", help="列出所有已注册的采集任务")

    # ---- run ----
    run_parser = subparsers.add_parser("run", help="运行指定任务")
    run_parser.add_argument(
        "task_name",
        type=str,
        help="要运行的任务名称",
    )

    # ---- status ----
    subparsers.add_parser("status", help="查看任务运行状态")

    # ---- add ----
    add_parser = subparsers.add_parser("add", help="注册新任务")
    add_parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="任务名称（唯一标识）",
    )
    add_parser.add_argument(
        "--description",
        type=str,
        default=None,
        help="任务描述（默认使用 name）",
    )
    add_parser.add_argument(
        "--type",
        type=str,
        default="meta",
        help=f"数据类型，可选: {', '.join(sorted(VALID_DATA_TYPES))}",
    )
    add_parser.add_argument(
        "--url",
        type=str,
        default="",
        help="目标 URL",
    )
    add_parser.add_argument(
        "--frequency",
        type=str,
        default="yearly",
        help=f"执行频率，可选: {', '.join(sorted(VALID_FREQUENCIES))}",
    )
    add_parser.add_argument(
        "--strategy",
        type=str,
        default="scrapy",
        help=f"采集策略，可选: {', '.join(sorted(VALID_STRATEGIES))}",
    )
    add_parser.add_argument(
        "--spider",
        type=str,
        default=None,
        help="爬虫文件路径（相对 spiders/ 目录）",
    )

    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    config = load_config()

    if args.command == "list":
        cmd_list(config)
    elif args.command == "run":
        cmd_run(config, args.task_name)
    elif args.command == "status":
        cmd_status(config)
    elif args.command == "add":
        cmd_add(config, args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
