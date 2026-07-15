#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
阳光高考院校满意度采集

来源：https://gaokao.chsi.com.cn/zyk/pub/myd/schAppraisalTop.action
采集在校生对母校的综合评分（满意度）

输出：data/raw/satisfaction/chsi_satisfaction.jsonl
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("chsi_satisfaction")

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "satisfaction"


@dataclass
class Satisfaction:
    school_name: str = ""
    overall: float = 0.0   # 综合满意度(1-5)
    environment: float = 0.0  # 环境满意度
    life: float = 0.0       # 生活满意度
    employment: float = 0.0  # 就业满意度
    vote_count: int = 0     # 投票人数
    data_source: str = "阳光高考"
    created_at: str = ""


class ChsiSatisfactionCollector:
    """阳光高考院校满意度采集"""

    BASE_URL = "https://gaokao.chsi.com.cn/zyk/pub/myd/schAppraisalTop.action"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://gaokao.chsi.com.cn/",
        })

    def run(self, dry_run: bool = False) -> List[Satisfaction]:
        results: List[Satisfaction] = []
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        page = 1
        while True:
            try:
                resp = self.session.get(self.BASE_URL, params={"pageno": page, "pagesize": 100}, timeout=15)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "html.parser")

                # 找表格行
                rows = soup.select("table tr") or soup.select(".listTable tr")
                if not rows:
                    # 尝试其他选择器
                    rows = soup.find_all("tr")

                if len(rows) <= 1:
                    break  # 只有表头，没有数据

                page_results = 0
                for row in rows[1:]:
                    cells = row.find_all("td")
                    if len(cells) < 6:
                        continue
                    try:
                        record = Satisfaction(
                            school_name=cells[0].get_text(strip=True),
                            overall=float(cells[1].get_text(strip=True) or 0),
                            environment=float(cells[3].get_text(strip=True) or 0),
                            life=float(cells[4].get_text(strip=True) or 0),
                            employment=float(cells[5].get_text(strip=True) or 0),
                            vote_count=int(re.sub(r"\D", "", cells[2].get_text(strip=True)) or 0),
                            data_source="阳光高考",
                            created_at=now_iso,
                        )
                        results.append(record)
                        page_results += 1
                    except (ValueError, IndexError):
                        continue

                if page_results == 0:
                    break

                logger.info("  第%d页: %d条", page, page_results)
                page += 1
                time.sleep(1)

                if dry_run and page > 2:
                    break
                if page > 50:  # 安全限制
                    break

            except Exception as e:
                logger.warning("第%d页异常: %s", page, e)
                break

        if dry_run:
            logger.info("== 预览: 前5条 ==")
            for r in results[:5]:
                print(f"  {r.school_name}: 综合{r.overall} 环境{r.environment} 生活{r.life} 就业{r.employment} ({r.vote_count}人投票)")

        logger.info("采集完成: %d 条", len(results))
        return results

    def save(self, records: List[Satisfaction]):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = DATA_DIR / "chsi_satisfaction.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
        logger.info("已保存: %s (%d 条)", path, len(records))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    c = ChsiSatisfactionCollector()
    records = c.run(dry_run=args.dry_run)
    if not args.dry_run and records:
        c.save(records)


if __name__ == "__main__":
    main()
