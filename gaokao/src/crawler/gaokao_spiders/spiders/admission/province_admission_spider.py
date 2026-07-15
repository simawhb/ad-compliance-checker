#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
省考试院录取数据通用爬虫 — 配置化驱动

每个省份只需在 PROVINCE_CONFIG 中配置：
  1. 首页URL
  2. 录取数据页面的链接匹配规则
  3. 表格解析规则

当前支持：山东、北京、上海

使用：
  python .../province_admission_spider.py --province 山东 --year 2025
  python .../province_admission_spider.py --province 北京 --year 2026 --dry-run
  python .../province_admission_spider.py --province 上海 --year 2025

输出：
  data/raw/admission/{province}/{year}/admission_{year}.jsonl
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
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("province_spider")

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DATA_BASE = PROJECT_ROOT / "data" / "raw" / "admission"


@dataclass
class AdmissionRecord:
    school_id: str = ""
    school_name: str = ""
    major_name: str = ""
    batch: str = ""
    plan_count: Optional[int] = None
    admit_score_min: Optional[float] = None
    admit_rank_min: Optional[int] = None
    year: int = 0
    province: str = ""
    data_source: str = ""
    data_confidence: str = "high"
    created_at: str = ""


class ProvinceAdmissionSpider:
    """省考试院录取数据通用爬虫"""

    # ========== 省份配置 ==========
    # 每省配置：首页、数据匹配关键词、输出省份名
    PROVINCE_CONFIG = {
        "山东": {
            "home_url": "https://www.sdzk.cn/",
            "encoding": "utf-8",
            "keywords": ["投档", "录取", "分数线", "志愿", "一段", "本科"],
            "links_selector": "a[href*='NewsInfo']",
            "province_name": "山东",
        },
        "北京": {
            "home_url": "https://www.bjeea.cn/html/gkgz/index.html",
            "encoding": "utf-8",
            "keywords": ["录取", "分数", "投档", "最低控制分数线"],
            "links_selector": "a[href*='html']",
            "province_name": "北京",
        },
        "广东": {
            "home_url": "https://eea.gd.gov.cn/",
            "encoding": "utf-8",
            "keywords": ["录取", "投档", "分数线", "分数段"],
            "links_selector": "a",
            "province_name": "广东",
        },
        "陕西": {
            "home_url": "https://www.sneea.cn/",
            "encoding": "utf-8",
            "keywords": ["录取", "投档", "分数线", "志愿"],
            "links_selector": "a",
            "province_name": "陕西",
        },
    }

    def __init__(self, province: str, year: int):
        self.province = province
        self.year = year
        self.config = self.PROVINCE_CONFIG.get(province)
        if not self.config:
            raise ValueError(f"不支持的省份: {province}，可选: {list(self.PROVINCE_CONFIG.keys())}")

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self.base_url = self.config["home_url"]

    def run(self, dry_run: bool = False) -> List[AdmissionRecord]:
        """主入口"""
        records: List[AdmissionRecord] = []
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        logger.info("开始采集 %s %d 年录取数据...", self.province, self.year)

        # 1. 获取首页，找录取数据链接
        data_urls = self._find_data_urls()
        if not data_urls:
            logger.warning("未找到录取数据页面链接")
            return []

        logger.info("找到 %d 个候选页面", len(data_urls))

        # 2. 访问每个候选页面，提取表格数据
        for url, title in data_urls[:3]:  # 最多取前3个最相关的页面
            page_records = self._parse_page(url, title)
            records.extend(page_records)

        # 3. 补全字段
        for r in records:
            r.year = self.year
            r.province = self.config["province_name"]
            r.data_source = f"{self.province}教育招生考试院"
            r.created_at = now_iso

        if dry_run:
            logger.info("== 预览: 前 5 条 ==")
            for r in records[:5]:
                print(f"  {r.school_name or '(未知)'} | {r.major_name or ''} | {r.batch} | "
                      f"分={r.admit_score_min} 位次={r.admit_rank_min}")

        logger.info("完成: %s %d, 共 %d 条", self.province, self.year, len(records))
        return records

    def _find_data_urls(self) -> List[Tuple[str, str]]:
        """从首页找到录取数据相关页面的链接"""
        urls: List[Tuple[str, str]] = []

        try:
            resp = self.session.get(self.base_url, timeout=15)
            resp.encoding = self.config.get("encoding", "utf-8")
            if resp.status_code != 200:
                logger.warning("首页访问失败: HTTP %d", resp.status_code)
                return urls

            soup = BeautifulSoup(resp.text, "html.parser")
            selector = self.config["links_selector"]
            links = soup.select(selector) or soup.find_all("a", href=True)

            for a in links:
                href = a.get("href", "")
                text = a.get_text(strip=True)
                if not href or not text:
                    continue

                full_url = urljoin(self.base_url, href)
                # 只收录包含年份+关键词的链接
                year_str = str(self.year)
                keywords = self.config["keywords"]
                has_year = year_str in text or year_str in href
                has_kw = any(kw in text for kw in keywords)

                if has_kw and has_year:
                    urls.append((full_url, text))

        except Exception as e:
            logger.error("首页访问异常: %s", e)

        return urls

    def _parse_page(self, url: str, title: str) -> List[AdmissionRecord]:
        """解析录取数据页面"""
        records: List[AdmissionRecord] = []

        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = "utf-8"
            if resp.status_code != 200:
                return records

            soup = BeautifulSoup(resp.text, "html.parser")

            # 尝试提取表格
            tables = soup.find_all("table")
            if not tables:
                # 没有table，看看有没有pre或div带数据的
                text = soup.get_text()
                records = self._parse_text_data(text, title)
                return records

            for table in tables:
                rows = table.find_all("tr")
                if len(rows) < 2:
                    continue

                # 第一行是表头
                headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
                col_map = self._identify_columns(headers)

                if not col_map.get("school_name"):
                    continue

                for row in rows[1:]:
                    cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                    record = self._parse_row(cells, col_map)
                    if record:
                        records.append(record)

        except Exception as e:
            logger.debug("解析页面异常 %s: %s", url[:50], e)

        return records

    def _parse_text_data(self, text: str, title: str) -> List[AdmissionRecord]:
        """从纯文本中提取录取数据（fallback）"""
        records: List[AdmissionRecord] = []

        # 常见格式：院校 专业 计划 分数 位次
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 5:
                # 尝试从数字中识别: 最后几位可能是分数和位次
                nums = []
                for p in parts:
                    cleaned = p.replace(",", "")
                    if cleaned.replace(".", "").isdigit():
                        nums.append(cleaned)

                if len(nums) >= 3:
                    try:
                        score = float(nums[-2])
                        rank = int(nums[-1])
                        if 200 <= score <= 780 and rank > 0:
                            # 前面的部分可能是院校名+专业名
                            text_parts = [p for p in parts if not p.replace(",", "").replace(".", "").isdigit()]
                            name = " ".join(text_parts)
                            record = AdmissionRecord(
                                school_name=name[:50] if name else title[:30],
                                admit_score_min=score,
                                admit_rank_min=rank,
                                batch=title[:20],
                            )
                            records.append(record)
                    except (ValueError, IndexError):
                        pass

        return records

    def _identify_columns(self, headers: List[str]) -> Dict[str, int]:
        """识别表格列"""
        col_map: Dict[str, int] = {}

        patterns = {
            "school_code": ["院校代码", "学校代码", "代号"],
            "school_name": ["院校名称", "学校名称", "高校名称", "招生院校", "院校"],
            "major_name": ["专业名称", "专业", "招生专业"],
            "plan_count": ["计划数", "招生计划", "计划"],
            "score_min": ["投档线", "最低分", "最低录取", "分数线", "录取分数"],
            "rank_min": ["最低位次", "位次", "投档位次", "录取位次"],
        }

        for idx, col_name in enumerate(headers):
            for field, keywords in patterns.items():
                if field in col_map:
                    continue
                for kw in keywords:
                    if kw in col_name:
                        col_map[field] = idx
                        break

        return col_map

    def _parse_row(self, cells: List[str], col_map: Dict[str, int]) -> Optional[AdmissionRecord]:
        """解析单行"""
        if not cells:
            return None

        def safe_get(idx: int) -> str:
            return cells[idx] if idx < len(cells) else ""

        record = AdmissionRecord()

        idx = col_map.get("school_code", -1)
        if idx >= 0:
            record.school_id = re.sub(r"\D", "", safe_get(idx))

        idx = col_map.get("school_name", -1)
        if idx >= 0:
            record.school_name = safe_get(idx)

        idx = col_map.get("major_name", -1)
        if idx >= 0:
            record.major_name = safe_get(idx)

        idx = col_map.get("plan_count", -1)
        if idx >= 0:
            try:
                record.plan_count = int(float(safe_get(idx)))
            except ValueError:
                pass

        idx = col_map.get("score_min", -1)
        if idx >= 0:
            try:
                record.admit_score_min = float(safe_get(idx))
            except ValueError:
                pass

        idx = col_map.get("rank_min", -1)
        if idx >= 0:
            try:
                record.admit_rank_min = int(float(safe_get(idx)))
            except ValueError:
                pass

        if not record.school_name:
            return None

        return record

    def save(self, records: List[AdmissionRecord]):
        out_dir = DATA_BASE / self.province / str(self.year)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"admission_{self.year}.jsonl"

        with open(out_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(asdict(r), ensure_ascii=False, default=str) + "\n")

        logger.info("已保存: %s (%d 条)", out_path, len(records))

        schools = set(r.school_name for r in records if r.school_name)
        print(f"\n{'='*60}")
        print(f"  {self.province} {self.year} 年录取数据")
        print(f"{'='*60}")
        print(f"  总记录数:  {len(records)}")
        print(f"  院校数:    {len(schools)}")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="省考试院录取数据通用爬虫")
    parser.add_argument("--province", required=True, choices=list(ProvinceAdmissionSpider.PROVINCE_CONFIG.keys()))
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    spider = ProvinceAdmissionSpider(province=args.province, year=args.year)
    records = spider.run(dry_run=args.dry_run)

    if not args.dry_run and records:
        spider.save(records)


if __name__ == "__main__":
    main()
