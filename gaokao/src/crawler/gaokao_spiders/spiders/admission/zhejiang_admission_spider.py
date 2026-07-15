#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
浙江考试院录取数据爬虫

从浙江省教育考试院发布的 PDF 中提取普通类平行投档数据。
PDF每年发布一册，包含全国高校在浙江的投档数据。

数据来源: https://www.zjzs.net/ 发布的 PDF 附件
输出格式: JSON Lines 到 data/raw/admission/zhejiang/{year}/

使用方式:
  python .../zhejiang_admission_spider.py --year 2024 --dry-run
  python .../zhejiang_admission_spider.py --year 2024 --download-only
  python .../zhejiang_admission_spider.py --year 2024
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import pdfplumber

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("zhejiang_admission")

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "admission" / "zhejiang"


@dataclass
class AdmissionRecord:
    """录取数据记录"""
    school_id: str = ""
    school_name: str = ""
    major_name: str = ""
    batch: str = ""
    plan_count: Optional[int] = None
    admit_score_min: Optional[float] = None
    admit_rank_min: Optional[int] = None
    year: int = 0
    province: str = "浙江"
    data_source: str = "浙江省教育考试院"
    data_confidence: str = "high"
    created_at: str = ""


class ZhejiangAdmissionSpider:
    """浙江录取数据爬虫"""

    # 已知 PDF URL 模板（年份需要替换）
    PDF_URLS = {
        2024: "https://www.zjzs.net/attach/0/a9189771c9514010accbac9b2699af95.pdf",
        # 2023以下URL可能需要从搜索中获得，暂时只硬编码2024
    }

    def __init__(self, year: int = 2024):
        self.year = year
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        })

    def run(self, dry_run: bool = False, download_only: bool = False) -> List[AdmissionRecord]:
        """主入口"""
        pdf_path = self._download_pdf()
        if not pdf_path:
            logger.error("PDF 下载失败")
            return []

        if download_only:
            logger.info("仅下载模式，已保存到: %s", pdf_path)
            return []

        records = self._parse_pdf(pdf_path)
        if dry_run:
            logger.info("== 预览: 前 5 条 ==")
            for r in records[:5]:
                print(json.dumps(asdict(r), ensure_ascii=False, default=str))

        logger.info("解析完成: 总计 %d 条", len(records))
        return records

    def _download_pdf(self) -> Optional[Path]:
        """下载 PDF"""
        url = self.PDF_URLS.get(self.year)
        if not url:
            logger.error("未知的年份: %d", self.year)
            return None

        out_dir = DATA_DIR / str(self.year)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "raw.pdf"

        if out_path.exists():
            logger.info("PDF 已存在: %s (跳过下载)", out_path)
            return out_path

        logger.info("正在下载: %s", url)
        try:
            resp = self.session.get(url, timeout=60)
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                f.write(resp.content)
            logger.info("已保存: %s (%d bytes)", out_path, len(resp.content))
            return out_path
        except Exception as e:
            logger.error("下载失败: %s", e)
            return None

    def _parse_pdf(self, pdf_path: Path) -> List[AdmissionRecord]:
        """解析 PDF 提取录取数据（基于文本行解析，适用于结构不标准的表格）"""
        records: List[AdmissionRecord] = []
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        # 跨页追踪当前院校名称
        current_school_name: Optional[str] = None

        with pdfplumber.open(pdf_path) as pdf:
            logger.info("PDF 共 %d 页", len(pdf.pages))

            # 跳到正文页（跳过封面/目录，约前12页）
            start_page = 12

            for page_idx, page in enumerate(pdf.pages):
                if page_idx < start_page:
                    continue

                text = page.extract_text()
                if not text:
                    continue

                lines = text.split("\n")
                records_from_page, current_school_name = self._parse_text_lines(
                    lines, page_idx + 1, current_school_name
                )
                records.extend(records_from_page)

                if (page_idx + 1) % 50 == 0:
                    logger.info("  已处理 %d/%d 页, 累计 %d 条",
                                page_idx + 1, len(pdf.pages), len(records))

        # 补全默认字段
        for r in records:
            r.year = self.year
            r.created_at = now_iso

        return records

    def _parse_text_lines(
        self, lines: List[str], page_num: int,
        prev_school: Optional[str] = None
    ) -> Tuple[List[AdmissionRecord], Optional[str]]:
        """从文本行中提取录取数据，返回(records, current_school_name)"""
        records: List[AdmissionRecord] = []
        current_school_name: Optional[str] = prev_school

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 跳过表头和页码
            if any(kw in line for kw in ["院校代", "选考科目范围", "平", "录",
                                          "浙江省", "年浙江省"]):
                continue

            # ---- 院校名称行匹配 ----
            # 查找行中是否包含 "(某地)" 模式——括号内容为城市名
            paren_match = re.search(r'\(([^)]+)\)', line)
            if paren_match:
                inner = paren_match.group(1).strip()
                # 城市名特征：以省/市/区/·结尾，纯中文，2-8字
                if re.match(r'^[\u4e00-\u9fff·]{2,8}$', inner) and \
                   (inner.endswith('省') or inner.endswith('市') or inner.endswith('区') or '·' in inner):
                    before = line[:paren_match.start()].strip()
                    before = re.sub(r'^\d{4}\s*', '', before).strip()
                    if before and len(before) >= 2 and len(before) <= 20:
                        current_school_name = before
                        # 如果这是纯院校行（行很短），跳过后面的数据解析
                        if len(line) < 30:
                            continue

            # 格式: 纯代码+院校名行（不带括号），如 "0001 北京大学"
            if current_school_name is None:
                simple_match = re.match(r'^(\d{4})\s+([^\d]{2,12})$', line)
                if simple_match:
                    current_school_name = simple_match.group(2).strip()
                    continue

            # ---- 专业数据行解析 ----
            parts = line.split()
            if len(parts) >= 6:
                try:
                    # 从右往左找到全部数字的位置和数量
                    numeric_positions = []
                    for i, p in enumerate(parts):
                        cleaned = p.replace(",", "")
                        if cleaned.replace(".", "").replace("-", "").isdigit():
                            numeric_positions.append(i)

                    if len(numeric_positions) < 5:
                        continue

                    # 数字序列结构（从右往左）：
                    # [二段位次] [二段最低分] [一段位次] [一段最低分] [均分] [学制] [计划]
                    # 或者只有一段时：
                    # [位次] [最低分] [均分] [学制] [计划]
                    nums = numeric_positions
                    plan = int(parts[nums[-5]])
                    score_idx = nums[-2]  # 最低分的位置（倒数第二个数字）
                    rank_idx = nums[-1]   # 位次的位置（最后一个数字）
                    min_score = float(parts[score_idx])
                    rank = int(parts[rank_idx])

                    # 专业名 = 数字序列之前的所有字段
                    major_name = " ".join(parts[:nums[-5]])

                    # 如果专业名中包含当前院校名（院校行可能混入数据），去除
                    if current_school_name and current_school_name in major_name:
                        major_name = major_name.replace(current_school_name, "").strip()
                    major_name = re.sub(r'^[&\s]+', '', major_name).strip()
                    # 专业名不能是纯括号内容（如"(浙江·舟山)"）
                    major_name = re.sub(r'^\([\u4e00-\u9fff·]+\)$', '', major_name).strip()

                    if 1 <= plan <= 999 and 200 <= min_score <= 780 and rank > 0 and current_school_name:
                        record = AdmissionRecord(
                            school_name=current_school_name,
                            major_name=major_name[:60],
                            plan_count=plan,
                            admit_score_min=min_score,
                            admit_rank_min=rank,
                            batch="普通类",
                        )
                        records.append(record)
                except (ValueError, IndexError, TypeError):
                    pass

        return records, current_school_name

    @staticmethod
    def _split_name(raw: str) -> Tuple[Optional[str], Optional[str]]:
        """尝试从文本中拆分院校名称和专业名称"""
        # 如果包含 "(北京)" 之类的地区，那这行很可能没有专业名
        # 或者院校名中包含括号
        raw = raw.strip()

        # 去掉末尾的(所在地)
        school = re.sub(r'\([^)]*\)$', '', raw).strip()
        if school != raw:
            return school, None

        return raw, None

    def save(self, records: List[AdmissionRecord]):
        """保存到文件"""
        out_dir = DATA_DIR / str(self.year)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"admission_{self.year}.jsonl"

        with open(out_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(asdict(r), ensure_ascii=False, default=str) + "\n")

        logger.info("已保存: %s (%d 条)", out_path, len(records))

        # 统计
        schools = set(r.school_name for r in records if r.school_name)
        majors = set(r.major_name for r in records if r.major_name)
        print(f"\n{'='*60}")
        print(f"  浙江 {self.year} 年录取数据 — 采集统计")
        print(f"{'='*60}")
        print(f"  总记录数:    {len(records)}")
        print(f"  涉及院校:    {len(schools)}")
        print(f"  涉及专业:    {len(majors)}")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="浙江考试院录取数据爬虫")
    parser.add_argument("--year", type=int, default=2024, help="数据年份")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    parser.add_argument("--download-only", action="store_true", help="仅下载PDF")
    args = parser.parse_args()

    spider = ZhejiangAdmissionSpider(year=args.year)
    records = spider.run(dry_run=args.dry_run, download_only=args.download_only)

    if not args.dry_run and not args.download_only and records:
        spider.save(records)


if __name__ == "__main__":
    main()
