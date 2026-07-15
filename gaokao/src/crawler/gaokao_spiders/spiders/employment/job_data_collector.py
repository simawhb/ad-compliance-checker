#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
招聘数据采集 — 每日采集各城市各专业的招聘岗位数据

数据来源：BOSS直聘公开搜索页面 + 智联招聘公开搜索
注意：只采集公开可见的岗位数量和薪资统计，不抓取个人简历信息。

使用：
  python .../job_data_collector.py
  python .../job_data_collector.py --dry-run
  python .../job_data_collector.py --city 西安 --city 成都

输出：
  data/raw/employment/jobs/YYYY-MM-DD.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("job_collector")

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "employment" / "jobs"


@dataclass
class JobStat:
    """招聘数据统计"""
    city: str = ""
    major_name: str = ""
    keyword: str = ""
    total_job_count: int = 0
    avg_salary: Optional[float] = None
    platform: str = ""
    year: int = 0
    month: int = 0
    data_source: str = ""
    created_at: str = ""


class JobDataCollector:
    """招聘数据采集器"""

    # 专业→搜索关键词映射
    MAJOR_KEYWORDS: Dict[str, List[str]] = {
        "计算机科学与技术": ["Java开发", "Python开发", "算法工程师", "软件开发", "前端开发"],
        "软件工程": ["软件工程师", "后端开发", "全栈工程师"],
        "电子信息工程": ["电子工程师", "嵌入式开发", "硬件工程师"],
        "通信工程": ["通信工程师", "网络工程师"],
        "自动化": ["自动化工程师", "PLC工程师", "控制工程师"],
        "机械设计制造及其自动化": ["机械设计", "机械工程师", "CAD"],
        "土木工程": ["土木工程师", "结构工程师", "施工员"],
        "会计学": ["会计", "财务", "审计"],
        "金融学": ["金融分析师", "证券", "银行"],
        "法学": ["法务", "律师", "法律顾问"],
        "临床医学": ["临床医生", "医师"],
        "护理学": ["护士", "护理"],
        "市场营销": ["市场专员", "品牌推广", "销售"],
        "汉语言文学": ["文案", "编辑", "行政"],
        "英语": ["英语翻译", "外贸", "英语教师"],
        "视觉传达设计": ["UI设计", "平面设计", "视觉设计"],
        "工商管理": ["项目经理", "产品经理", "运营"],
        "数据科学与大数据技术": ["数据分析师", "大数据开发", "数据挖掘"],
        "人工智能": ["AI工程师", "机器学习", "深度学习"],
        "电子商务": ["电商运营", "新媒体运营", "直播运营"],
    }

    # 核心城市（首批）
    CITIES = [
        "西安", "成都", "郑州", "武汉", "长沙",
        "北京", "上海", "广州", "深圳", "杭州",
        "南京", "重庆", "苏州", "合肥", "天津",
    ]

    def __init__(self, cities: Optional[List[str]] = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        })
        self.cities = cities or self.CITIES

    def run(self, dry_run: bool = False) -> List[JobStat]:
        """主入口"""
        all_stats: List[JobStat] = []
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        now = datetime.now()

        total_tasks = len(self.cities) * sum(len(kws) for kws in self.MAJOR_KEYWORDS.values())

        for city in self.cities[:5] if dry_run else self.cities:
            logger.info("城市: %s", city)
            for major, keywords in self.MAJOR_KEYWORDS.items():
                # 每天只搜索每个专业的第一个关键词（减少请求量）
                kw = keywords[0]
                stats = self._search_boss(city, kw, major)
                all_stats.extend(stats)
                time.sleep(1)  # 礼貌间隔

                if dry_run and len(all_stats) >= 5:
                    break
            if dry_run and len(all_stats) >= 5:
                break

        for s in all_stats:
            s.year = now.year
            s.month = now.month
            s.created_at = now_iso

        if dry_run:
            logger.info("== 预览: 前 5 条 ==")
            for s in all_stats[:5]:
                print(f"  {s.city} | {s.major_name} | {s.keyword} | {s.total_job_count}岗位 | {s.avg_salary}K")

        logger.info("采集完成: %d 条统计", len(all_stats))
        return all_stats

    def _search_boss(self, city: str, keyword: str, major: str) -> List[JobStat]:
        """搜索 BOSS直聘"""
        stats: List[JobStat] = []

        try:
            # BOSS直聘搜索API
            url = "https://www.zhipin.com/web/geek/job"
            params = {
                "query": keyword,
                "city": city,
                "page": 1,
            }
            resp = self.session.get(url, params=params, timeout=15)

            if resp.status_code != 200:
                logger.debug("BOSS %s/%s: HTTP %d", city, keyword, resp.status_code)
                return stats

            # 从页面提取岗位数量和薪资信息
            soup = BeautifulSoup(resp.text, "html.parser")

            # 岗位总数
            count_el = soup.select_one(".job-count") or soup.select_one(".search-count")
            total = 0
            if count_el:
                text = count_el.get_text(strip=True)
                nums = re.findall(r'\d+', text)
                total = int(nums[0]) if nums else 0

            # 平均薪资（从列表中的岗位估算）
            salary_elements = soup.select(".salary") or soup.select(".job-list-item .red") or []
            salaries = []
            for el in salary_elements[:30]:
                text = el.get_text(strip=True)
                nums = re.findall(r'(\d+)K?', text)
                if len(nums) >= 2:
                    salaries.append((int(nums[0]) + int(nums[1])) / 2)
                elif nums:
                    salaries.append(float(nums[0]))

            avg_sal = round(sum(salaries) / len(salaries), 1) if salaries else None

            if total > 0:
                stats.append(JobStat(
                    city=city,
                    major_name=major,
                    keyword=keyword,
                    total_job_count=total,
                    avg_salary=avg_sal,
                    platform="BOSS直聘",
                    data_source="www.zhipin.com",
                ))

        except Exception as e:
            logger.debug("BOSS采集异常 %s/%s: %s", city, keyword, e)

        return stats

    def save(self, stats: List[JobStat], output_dir: Optional[Path] = None):
        out = output_dir or DATA_DIR
        out.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        out_path = out / f"{today}.jsonl"

        with open(out_path, "w", encoding="utf-8") as f:
            for s in stats:
                f.write(json.dumps(asdict(s), ensure_ascii=False, default=str) + "\n")

        logger.info("已保存: %s (%d 条)", out_path, len(stats))

        total_jobs = sum(s.total_job_count for s in stats)
        print(f"\n{'='*60}")
        print(f"  招聘数据 — 采集统计")
        print(f"{'='*60}")
        print(f"  统计条数:  {len(stats)}")
        print(f"  覆盖城市:  {len(set(s.city for s in stats))}")
        print(f"  覆盖专业:  {len(set(s.major_name for s in stats))}")
        print(f"  总岗位数:  {total_jobs:,}")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="招聘数据采集")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--city", action="append", help="指定城市（可多次）")
    args = parser.parse_args()

    collector = JobDataCollector(cities=args.city)
    stats = collector.run(dry_run=args.dry_run)

    if not args.dry_run and stats:
        collector.save(stats)


if __name__ == "__main__":
    main()
