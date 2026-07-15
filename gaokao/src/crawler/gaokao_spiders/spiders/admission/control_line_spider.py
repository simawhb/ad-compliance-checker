#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
省控线数据采集爬虫

从各省教育考试院官网抓取省控线（录取最低控制分数线），
解析为结构化数据，输出到 data/raw/admission/control_lines/ 下的jsonl文件。

数据来源（已确认可访问）:
  北京: https://www.bjeea.cn/html/gkgz/tzgg/2026/0624/88239.html
  广东: https://eea.gd.gov.cn/ptgk/content/post_4915151.html
  山东: sdzk.cn 上的 NewsInfo 页面
  陕西: sneea.cn 上的省控线公告

使用方法:
  python .../control_line_spider.py --province 北京 --year 2026
  python .../control_line_spider.py --province 广东 --year 2026
  python .../control_line_spider.py --all  # 抓取所有已配置省份
"""

from __future__ import annotations

import argparse
import json
import logging
import html as html_mod
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("control_line_spider")

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "admission" / "control_lines"


@dataclass
class ControlLineRecord:
    """省控线记录"""
    province: str = ""
    year: int = 2026
    batch: str = ""          # 本科/专科/特控/艺术/体育/高职单招
    category: str = ""        # 物理/历史/普通/综合
    score: int = 0
    data_source: str = ""     # URL
    created_at: str = ""


class ControlLineSpider:
    """省控线爬虫基类"""

    PROVINCE_CONFIG: Dict[str, Dict[str, Any]] = {}

    def __init__(self, province: str, year: int = 2026):
        self.province = province
        self.year = year
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        })
        self.created_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    def fetch_text(self, url: str) -> str:
        """获取页面文本内容"""
        logger.info("正在抓取: %s", url)
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        # 强制用 utf-8 解码
        try:
            text = resp.content.decode('utf-8')
        except UnicodeDecodeError:
            text = resp.text
        logger.info("页面大小: %d bytes", len(text))
        return text

    def parse(self, html: str) -> List[ControlLineRecord]:
        """子类需实现此方法"""
        raise NotImplementedError

    def run(self) -> List[ControlLineRecord]:
        """主入口"""
        config = self.PROVINCE_CONFIG.get(self.province)
        if not config:
            logger.error("未配置省份: %s", self.province)
            return []
        url = config.get("url")
        if not url:
            logger.error("省份 %s 未配置 URL", self.province)
            return []

        html = self.fetch_text(url)
        records = self.parse(html)
        # 补全公共字段
        for r in records:
            r.province = self.province
            r.year = self.year
            r.data_source = url
            r.created_at = self.created_at
        logger.info("解析完成: %s %d年 共 %d 条", self.province, self.year, len(records))
        return records

    def save(self, records: List[ControlLineRecord]):
        """保存到jsonl文件"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        out_path = DATA_DIR / f"{self.province}_{self.year}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
        logger.info("已保存: %s (%d 条)", out_path, len(records))

    @staticmethod
    def _extract_int(text: str) -> Optional[int]:
        """从文本中提取整数分数"""
        m = re.search(r'(\d+)分?', text)
        if m:
            return int(m.group(1))
        return None

    @staticmethod
    def _clean_text(text: str) -> str:
        """清理文本空白字符"""
        text = re.sub(r'\s+', '', text)
        return text.strip()


class BeijingSpider(ControlLineSpider):
    """北京省控线爬虫"""

    PROVINCE_CONFIG = {
        "北京": {
            "url": "https://www.bjeea.cn/html/gkgz/tzgg/2026/0624/88239.html",
        }
    }

    def parse(self, html: str) -> List[ControlLineRecord]:
        records = []
        # 先去掉 HTML 标签和 &nbsp; 等实体
        clean = re.sub(r'<[^>]+>', '', html)
        clean = html_mod.unescape(clean)
        clean = re.sub(r'\s+', '', clean)

        # 普通本科录取控制分数线429分
        patterns = [
            (r'普通本科录取控制分数线(\d+)', "本科", "综合"),
            (r'特殊类型招生控制分数线(\d+)', "特控", "综合"),
            (r'艺术类（不含舞蹈类、戏曲类）本科录取控制分数线(\d+)', "艺术本科", "综合"),
            (r'舞蹈类、戏曲类本科录取控制分数线(\d+)', "艺术本科", "舞蹈戏曲"),
            (r'体育类本科录取控制分数线[（(]体育成绩60分[）)](\d+)', "体育本科", "综合"),
            (r'普通专科录取控制分数线(\d+)', "专科", "综合"),
            (r'艺术类专科录取控制分数线(\d+)', "艺术专科", "综合"),
            (r'高职单考单招控制分数线(\d+)', "高职单招", "综合"),
            (r'高职单考单招艺术类专业控制分数线(\d+)', "高职单招", "艺术"),
        ]

        for pattern, batch, category in patterns:
            m = re.search(pattern, clean)
            if m:
                score = int(m.group(1))
                records.append(ControlLineRecord(
                    batch=batch,
                    category=category,
                    score=score,
                ))
                logger.info("  北京 %s(%s): %d分", batch, category, score)
            else:
                logger.warning("  北京 %s(%s): 未匹配", batch, category)

        return records


class GuangdongSpider(ControlLineSpider):
    """广东省控线爬虫"""

    PROVINCE_CONFIG = {
        "广东": {
            "url": "https://eea.gd.gov.cn/ptgk/content/post_4915151.html",
        }
    }

    def parse(self, html: str) -> List[ControlLineRecord]:
        records = []
        # 先去掉 HTML 标签和 &nbsp; 等实体
        clean = re.sub(r'<[^>]+>', '', html)
        clean = html_mod.unescape(clean)
        clean = re.sub(r'\s+', '', clean)

        # 本科 - 普通类（历史）：总分440分。
        m = re.search(r'本科各科类.*?普通类（历史）[：:]\s*总分(\d+)', clean)
        if m:
            records.append(ControlLineRecord(batch="本科", category="历史", score=int(m.group(1))))
        m = re.search(r'本科各科类.*?普通类（物理）[：:]\s*总分(\d+)', clean)
        if m:
            records.append(ControlLineRecord(batch="本科", category="物理", score=int(m.group(1))))

        # 特控线
        m = re.search(r'特殊类型招生录取控制线[^。]*?普通类（历史）[：:]\s*总分(\d+)', clean)
        if m:
            records.append(ControlLineRecord(batch="特控", category="历史", score=int(m.group(1))))
        m = re.search(r'特殊类型招生录取控制线[^。]*?普通类（物理）[：:]\s*总分(\d+)', clean)
        if m:
            records.append(ControlLineRecord(batch="特控", category="物理", score=int(m.group(1))))

        # 地方专项
        m = re.search(r'地方专项计划[^。]*?普通类（历史）[：:]\s*总分(\d+)', clean)
        if m:
            records.append(ControlLineRecord(batch="地方专项", category="历史", score=int(m.group(1))))
        m = re.search(r'地方专项计划[^。]*?普通类（物理）[：:]\s*总分(\d+)', clean)
        if m:
            records.append(ControlLineRecord(batch="地方专项", category="物理", score=int(m.group(1))))

        # 专科
        m = re.search(r'专科院校[^。]*?普通类（历史）[：:]\s*总分(\d+)', clean)
        if m:
            records.append(ControlLineRecord(batch="专科", category="历史", score=int(m.group(1))))
        m = re.search(r'专科院校[^。]*?普通类（物理）[：:]\s*总分(\d+)', clean)
        if m:
            records.append(ControlLineRecord(batch="专科", category="物理", score=int(m.group(1))))

        for r in records:
            logger.info("  广东 %s(%s): %d分", r.batch, r.category, r.score)

        if not records:
            logger.warning("  广东: 未匹配到任何分数线，检查页面结构")

        return records


# ── 爬虫注册表 ────────────────────────────────────────────────────────

SPIDER_REGISTRY = {
    "北京": BeijingSpider,
    "广东": GuangdongSpider,
}

# 公共配置（所有爬虫共享）
PROVINCE_URLS = {}
for spider_cls in SPIDER_REGISTRY.values():
    PROVINCE_URLS.update(spider_cls.PROVINCE_CONFIG)


def get_spider(province: str, year: int = 2026) -> ControlLineSpider:
    """工厂方法：获取对应省份的爬虫实例"""
    cls = SPIDER_REGISTRY.get(province)
    if not cls:
        raise ValueError(f"不支持的省份: {province}，可用: {list(SPIDER_REGISTRY.keys())}")
    return cls(province=province, year=year)


def main():
    parser = argparse.ArgumentParser(description="省控线数据采集爬虫")
    parser.add_argument("--province", type=str, default=None, help="省份名称")
    parser.add_argument("--year", type=int, default=2026, help="数据年份")
    parser.add_argument("--all", action="store_true", help="抓取所有已配置省份")
    parser.add_argument("--dry-run", action="store_true", help="仅打印不保存")
    parser.add_argument("--list", action="store_true", help="列出所有已配置省份")
    args = parser.parse_args()

    if args.list:
        print("已配置的省份:")
        for p in sorted(SPIDER_REGISTRY.keys()):
            cfg = SPIDER_REGISTRY[p].PROVINCE_CONFIG.get(p, {})
            url = cfg.get("url", "N/A")
            print(f"  - {p}: {url}")
        return

    provinces = []
    if args.all:
        provinces = list(SPIDER_REGISTRY.keys())
    elif args.province:
        provinces = [args.province]
    else:
        parser.print_help()
        print("\n请使用 --province 指定省份，或使用 --all 抓取所有省份")
        return

    for province in provinces:
        try:
            spider = get_spider(province, args.year)
            records = spider.run()
            if not args.dry_run and records:
                spider.save(records)
            elif args.dry_run:
                print(f"\n{province} {args.year}年省控线 (预览):")
                for r in records:
                    print(f"  {r.batch:10s} {r.category:6s} {r.score}分")
        except Exception as e:
            logger.error("抓取 %s 失败: %s", province, e, exc_info=True)


if __name__ == "__main__":
    main()
