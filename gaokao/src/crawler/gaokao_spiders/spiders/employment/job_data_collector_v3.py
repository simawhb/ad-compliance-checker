#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
招聘数据采集 v3 — Playwright 浏览器自动化版

用真实浏览器抓取智联招聘公开数据，绕过反爬。
每日采集各城市各专业的关键词岗位数量和薪资。

使用：
  python .../job_data_collector_v3.py
  python .../job_data_collector_v3.py --dry-run

依赖：
  pip install playwright
  playwright install chromium

输出：
  data/raw/employment/jobs/YYYY-MM-DD.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("job_v3")

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "employment" / "jobs"


@dataclass
class JobStatV3:
    city: str = ""
    major_keyword: str = ""
    total_job_count: int = 0
    avg_salary_min: Optional[float] = None
    avg_salary_max: Optional[float] = None
    sample_jobs: List[dict] = None
    platform: str = "智联招聘"
    year: int = 0
    month: int = 0
    created_at: str = ""


class JobCollectorV3:
    """招聘数据采集器 v3 — Playwright 驱动"""

    # 专业→智联搜索关键词（与各专业最匹配的岗位搜索词）
    MAJOR_KEYWORDS: Dict[str, List[str]] = {
        "计算机科学与技术": ["Java开发", "Python开发", "软件开发"],
        "软件工程": ["软件工程师", "后端开发"],
        "电子信息工程": ["电子工程师", "嵌入式"],
        "通信工程": ["通信工程师", "网络工程师"],
        "自动化": ["自动化工程师", "PLC"],
        "机械设计制造及其自动化": ["机械设计", "机械工程师"],
        "土木工程": ["土木工程师", "结构工程师"],
        "会计学": ["会计", "财务"],
        "金融学": ["金融分析师", "证券"],
        "法学": ["法务", "律师"],
        "临床医学": ["临床医生", "医师"],
        "护理学": ["护士", "护理"],
        "市场营销": ["市场专员", "销售"],
        "汉语言文学": ["文案", "编辑", "行政"],
        "英语": ["英语翻译", "外贸"],
        "视觉传达设计": ["UI设计", "平面设计"],
        "工商管理": ["产品经理", "项目经理"],
        "数据科学与大数据技术": ["数据分析师", "大数据"],
        "人工智能": ["AI工程师", "机器学习"],
        "电子商务": ["电商运营", "新媒体运营"],
    }

    CITIES = [
        "西安", "成都", "郑州", "武汉", "长沙",
        "北京", "上海", "广州", "深圳", "杭州",
        "南京", "重庆", "苏州", "合肥", "天津",
    ]

    def __init__(self, cities: Optional[List[str]] = None):
        self.cities = cities or self.CITIES
        self._playwright = None
        self._browser = None
        self._page = None

    def _ensure_browser(self):
        """确保浏览器实例可用"""
        if self._page:
            return
        from playwright.sync_api import sync_playwright
        self._playwright = sync_playwright().__enter__()
        self._browser = self._playwright.chromium.launch(headless=True)
        ctx = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        self._page = ctx.new_page()

    def _close_browser(self):
        """关闭浏览器"""
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.__exit__(None, None, None)
        except Exception:
            pass
        self._playwright = None
        self._browser = None
        self._page = None

    def run(self, dry_run: bool = False) -> List[JobStatV3]:
        """主入口"""
        all_stats: List[JobStatV3] = []
        now = datetime.now()
        now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            self._ensure_browser()

            total_tasks = len(self.cities) * len(self.MAJOR_KEYWORDS)
            task_count = 0

            for city in self.cities[:3] if dry_run else self.cities:
                for major, keywords in self.MAJOR_KEYWORDS.items():
                    kw = keywords[0]  # 每种专业只搜第一个关键词
                    stats = self._search_zhaopin(city, kw, major)
                    all_stats.extend(stats)
                    task_count += 1

                    if task_count % 10 == 0:
                        logger.info("  进度: %d/%d", task_count, total_tasks)

                    if dry_run and task_count >= 5:
                        break
                if dry_run and task_count >= 5:
                    break

            for s in all_stats:
                s.year = now.year
                s.month = now.month
                s.created_at = now_iso

        finally:
            self._close_browser()

        if dry_run:
            logger.info("== 预览: 前 5 条 ==")
            for s in all_stats[:5]:
                sample = s.sample_jobs[0] if s.sample_jobs else {}
                print(f"  {s.city:4s} | {s.major_keyword:12s} | {s.total_job_count}岗位 | "
                      f"薪资{s.avg_salary_min}-{s.avg_salary_max}K")

        logger.info("采集完成: %d 条统计", len(all_stats))
        return all_stats

    def _search_zhaopin(self, city: str, keyword: str, major: str) -> List[JobStatV3]:
        """智联招聘搜索 — 基于文本解析"""
        import urllib.parse

        kw_encoded = urllib.parse.quote(keyword)
        city_encoded = urllib.parse.quote(city)
        url = f"https://www.zhaopin.com/sou/?kw={kw_encoded}&city={city_encoded}&p=1"

        stats: List[JobStatV3] = []

        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)

            text = self._page.inner_text("body")

            # 从文本中解析岗位
            # 智联页面上的岗位格式：
            # 标题
            # 薪资
            # 标签
            # 公司 · 地点 · 经验 · 学历
            # 公司名
            # 行业

            # 提取薪资
            salary_pairs = re.findall(
                r'([\d.]+)-([\d.]+)[万万千]*[/月]*',
                text
            )

            # 提取岗位标题（通常在薪资前面，包含关键词的行）
            lines = text.split('\n')
            job_entries = []
            current_entry = {}
            job_count = 0

            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    if current_entry.get("title"):
                        job_entries.append(current_entry)
                        current_entry = {}
                    continue

                # 检测是否为岗位标题（通常包含搜索关键词）
                if keyword[:2] in line and len(line) < 50 and job_count < 10:
                    # 看后面几行是否有薪资
                    salary_text = ""
                    for j in range(i + 1, min(i + 5, len(lines))):
                        next_line = lines[j].strip()
                        if re.match(r'[\d.]+-[\d.]+[万千]', next_line):
                            salary_text = next_line
                            break
                    current_entry = {"title": line, "salary": salary_text}
                    job_count += 1

            # 提取薪资数据
            salaries_min, salaries_max = [], []
            for entry in job_entries:
                salary_text = entry.get("salary", "")
                nums = re.findall(r'([\d.]+)', salary_text)
                if len(nums) >= 2:
                    unit = "万" if "万" in salary_text else "千"
                    s_min = float(nums[0]) * (10 if unit == "千" else 10)
                    s_max = float(nums[1]) * (10 if unit == "千" else 10)
                    salaries_min.append(s_min)
                    salaries_max.append(s_max)

            # 如果岗位数太少，尝试统计总岗位数
            if not job_entries:
                # 从页面文本统计包含关键字+薪资的行
                all_salaries = re.findall(r'[\d.]+-[\d.]+[万万千]', text)
                job_count = len(all_salaries)
                for s in all_salaries:
                    nums = re.findall(r'([\d.]+)', s)
                    if len(nums) >= 2:
                        unit = "万" if "万" in s else "千"
                        salaries_min.append(float(nums[0]) * (10 if unit == "千" else 10))
                        salaries_max.append(float(nums[1]) * (10 if unit == "千" else 10))

            avg_min = round(sum(salaries_min) / len(salaries_min), 1) if salaries_min else None
            avg_max = round(sum(salaries_max) / len(salaries_max), 1) if salaries_max else None

            if job_count > 0:
                sample_jobs = [{"title": e.get("title", ""), "salary": e.get("salary", "")}
                               for e in job_entries[:5]]

                stat = JobStatV3(
                    city=city,
                    major_keyword=major,
                    total_job_count=job_count,
                    avg_salary_min=avg_min,
                    avg_salary_max=avg_max,
                    sample_jobs=sample_jobs,
                    platform="智联招聘",
                )
                stats.append(stat)

            logger.debug("  %s/%s: %d 岗位, 薪资 %s-%sK",
                         city, keyword, job_count, avg_min, avg_max)

        except Exception as e:
            logger.debug("  %s/%s: %s", city, keyword, e)

        return stats

    def save(self, stats: List[JobStatV3], output_dir: Optional[Path] = None):
        out = output_dir or DATA_DIR
        out.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        out_path = out / f"zhaopin_{today}.jsonl"

        with open(out_path, "w", encoding="utf-8") as f:
            for s in stats:
                f.write(json.dumps(asdict(s), ensure_ascii=False, default=str) + "\n")

        logger.info("已保存: %s (%d 条)", out_path, len(stats))

        total_jobs = sum(s.total_job_count for s in stats)
        cities = set(s.city for s in stats)
        print(f"\n{'='*60}")
        print(f"  招聘数据(智联) — 采集统计")
        print(f"{'='*60}")
        print(f"  统计条数:  {len(stats)}")
        print(f"  覆盖城市:  {len(cities)}")
        print(f"  覆盖专业:  {len(set(s.major_keyword for s in stats))}")
        print(f"  总岗位数:  {total_jobs}")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="招聘数据采集 v3 — Playwright")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--city", action="append", help="指定城市")
    args = parser.parse_args()

    collector = JobCollectorV3(cities=args.city)
    stats = collector.run(dry_run=args.dry_run)

    if not args.dry_run and stats:
        collector.save(stats)


if __name__ == "__main__":
    main()
