#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
招聘数据采集 v3-final — Playwright 浏览器自动化版

用真实浏览器抓取智联招聘公开数据，每日采集各城市各专业的岗位数量和薪资。

使用：
  python .../job_collector_final.py
  python .../job_collector_final.py --dry-run

输出：
  data/raw/employment/jobs/zhaopin_YYYY-MM-DD.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import urllib.parse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("job_final")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "employment" / "jobs"


@dataclass
class JobStat:
    city: str = ""
    major_keyword: str = ""
    total_job_count: int = 0
    avg_salary_min: Optional[float] = None
    avg_salary_max: Optional[float] = None
    platform: str = "智联招聘"
    year: int = 0
    month: int = 0
    created_at: str = ""


class JobCollectorFinal:
    """招聘采集器 — Playwright + 智联招聘"""

    # 专业→搜索关键词（每个专业只取第一个，减少采集量）
    MAJOR_KEYWORDS: Dict[str, List[str]] = {
        "计算机科学与技术": ["Java开发"],
        "软件工程": ["软件工程师"],
        "电子信息工程": ["电子工程师"],
        "通信工程": ["通信工程师"],
        "自动化": ["自动化工程师"],
        "机械设计制造及其自动化": ["机械设计"],
        "土木工程": ["土木工程师"],
        "会计学": ["会计"],
        "金融学": ["金融"],
        "法学": ["法务"],
        "临床医学": ["临床医生"],
        "护理学": ["护士"],
        "市场营销": ["市场专员"],
        "汉语言文学": ["编辑"],
        "英语": ["英语翻译"],
        "视觉传达设计": ["平面设计"],
        "工商管理": ["产品经理"],
        "数据科学与大数据技术": ["数据分析师"],
        "人工智能": ["AI工程师"],
        "电子商务": ["电商运营"],
    }

    CITIES = ["西安", "成都", "郑州", "武汉", "长沙",
              "北京", "上海", "广州", "杭州", "南京"]

    # 快速模式：仅采集前三城市（用于每日巡检，减少超时风险）
    QUICK_CITIES = ["西安", "成都", "北京"]

    def __init__(self, cities: Optional[List[str]] = None, quick: bool = False):
        if quick:
            self.cities = cities or self.QUICK_CITIES
        else:
            self.cities = cities or self.CITIES
        self._playwright = None
        self._browser = None
        self._page = None

    def _init_browser(self):
        from playwright.sync_api import sync_playwright
        self._playwright = sync_playwright().__enter__()
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        ctx = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        ctx.add_init_script(
            'Object.defineProperty(navigator,"webdriver",{get:()=>undefined})'
        )
        self._page = ctx.new_page()

    def _close_browser(self):
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.__exit__(None, None, None)
        except Exception:
            pass

    def run(self, dry_run: bool = False) -> List[JobStat]:
        all_stats: List[JobStat] = []
        now = datetime.now()

        try:
            self._init_browser()

            cities = self.cities[:3] if dry_run else self.cities
            for city in cities:
                for major, keywords in self.MAJOR_KEYWORDS.items():
                    kw = keywords[0]
                    stat = self._search(city, kw, major)
                    if stat:
                        stat.year = now.year
                        stat.month = now.month
                        stat.created_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
                        all_stats.append(stat)

            if dry_run:
                for s in all_stats[:5]:
                    print(f"  {s.city:4s} | {s.major_keyword:12s} | {s.total_job_count}岗位 | "
                          f"{s.avg_salary_min}-{s.avg_salary_max}K")

        finally:
            self._close_browser()

        logger.info("采集完成: %d 条", len(all_stats))
        return all_stats

    def _search(self, city: str, keyword: str, major: str) -> Optional[JobStat]:
        url = f"https://www.zhaopin.com/sou/?kw={urllib.parse.quote(keyword)}&city={urllib.parse.quote(city)}&p=1"
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)
            text = self._page.inner_text("body")

            salaries = re.findall(r"([\d.]+)-([\d.]+)([万万千])", text)
            job_titles = [
                l.strip() for l in text.split("\n")
                if keyword[:2] in l and len(l.strip()) < 40 and l.strip()
            ]

            s_min_vals, s_max_vals = [], []
            for sm, sx, unit in salaries:
                u = 10
                s_min_vals.append(float(sm) * u)
                s_max_vals.append(float(sx) * u)

            avg_min = round(sum(s_min_vals) / len(s_min_vals), 1) if s_min_vals else None
            avg_max = round(sum(s_max_vals) / len(s_max_vals), 1) if s_max_vals else None

            logger.debug("  %s/%s: %d 岗位 %s-%sK", city, keyword, len(job_titles), avg_min, avg_max)

            return JobStat(
                city=city,
                major_keyword=major,
                total_job_count=len(job_titles),
                avg_salary_min=avg_min,
                avg_salary_max=avg_max,
                platform="智联招聘",
            )
        except Exception as e:
            logger.debug("  %s/%s: %s", city, keyword, e)
            return None

    def save(self, stats: List[JobStat]):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        path = DATA_DIR / f"zhaopin_{today}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for s in stats:
                f.write(json.dumps(asdict(s), ensure_ascii=False, default=str) + "\n")
        logger.info("已保存: %s (%d 条)", path, len(stats))
        total = sum(s.total_job_count for s in stats)
        print(f"\n{'='*60}")
        print(f"  智联招聘 — 采集统计")
        print(f"{'='*60}")
        print(f"  统计条数:  {len(stats)}")
        print(f"  覆盖城市:  {len(set(s.city for s in stats))}")
        print(f"  覆盖专业:  {len(set(s.major_keyword for s in stats))}")
        print(f"  总岗位数:  {total}")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="招聘采集 v3-final")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--city", action="append")
    args = parser.parse_args()

    c = JobCollectorFinal(cities=args.city)
    stats = c.run(dry_run=args.dry_run)
    if not args.dry_run and stats:
        c.save(stats)


if __name__ == "__main__":
    main()
