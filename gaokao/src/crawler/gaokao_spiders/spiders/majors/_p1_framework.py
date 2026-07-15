#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
教育部本科/专科专业目录爬虫
==============================
内置 2024 年本科专业目录 & 2021 年职业教育专业目录数据。
独立运行 + Scrapy 集成，输出 JSON Lines 到 data/raw/majors/。

使用方式：
  python src/crawler/gaokao_spiders/spiders/majors/moe_majors_spider.py
  python src/crawler/gaokao_spiders/spiders/majors/moe_majors_spider.py --dry-run
  cd src/crawler && scrapy crawl moe_majors
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Scrapy 可选导入
# ---------------------------------------------------------------------------
HAS_SCRAPY = False
CrawlerProcess = None
_SpiderBase = object

try:
    import scrapy
    from scrapy.crawler import CrawlerProcess
    _SpiderBase = scrapy.Spider
    HAS_SCRAPY = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).resolve().parents[5] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(
            LOG_DIR / f"moe_majors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("moe_majors")

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
MOE_MAJOR_INDEX_URL = "http://www.moe.gov.cn/s78/A08/gjs_left/moe_1034/"
CHSI_MAJOR_URL = "https://gaokao.chsi.com.cn/zyk/"
KNOWN_MAJOR_URLS = [
    "http://www.moe.gov.cn/srcsite/A08/moe_1034/s4930/202403/t20240319_1121111.html",
    "http://www.moe.gov.cn/srcsite/A08/moe_1034/s4930/202304/t20230404_1054230.html",
]
OUTPUT_DIR = Path(__file__).resolve().parents[5] / "data" / "raw" / "majors"
SCRAPY_PROJECT_DIR = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# 学科门类定义
# ---------------------------------------------------------------------------
UNDERGRAD_CATEGORIES: Dict[str, str] = {
    "01": "哲学", "02": "经济学", "03": "法学", "04": "教育学",
    "05": "文学", "06": "历史学", "07": "理学", "08": "工学",
    "09": "农学", "10": "医学", "12": "管理学", "13": "艺术学",
}

VOCATIONAL_CATEGORIES: Dict[str, str] = {
    "41": "农林牧渔大类", "42": "资源环境与安全大类",
    "43": "能源动力与材料大类", "44": "土木建筑大类",
    "45": "水利大类", "46": "装备制造大类",
    "47": "生物与化工大类", "48": "轻工纺织大类",
    "49": "食品药品与粮食大类", "50": "交通运输大类",
    "51": "电子与信息大类", "52": "医药卫生大类",
    "53": "财经商贸大类", "54": "旅游大类",
    "55": "文化艺术大类", "56": "新闻传播大类",
    "57": "教育与体育大类", "58": "公安与司法大类",
    "59": "公共管理与服务大类",
}

UNDERGRAD_SUB_CATEGORIES: Dict[str, Tuple[str, str]] = {
    "0101": ("哲学类", "01"), "0201": ("经济学类", "02"),
    "0202": ("财政学类", "02"), "0203": ("金融学类", "02"),
    "0204": ("经济与贸易类", "02"), "0301": ("法学类", "03"),
    "0302": ("政治学类", "03"), "0303": ("社会学类", "03"),
    "0304": ("民族学类", "03"), "0305": ("马克思主义理论类", "03"),
    "0306": ("公安学类", "03"), "0401": ("教育学类", "04"),
    "0402": ("体育学类", "04"), "0501": ("中国语言文学类", "05"),
    "0502": ("外国语言文学类", "05"), "0503": ("新闻传播学类", "05"),
    "0601": ("历史学类", "06"), "0701": ("数学类", "07"),
    "0702": ("物理学类", "07"), "0703": ("化学类", "07"),
    "0704": ("天文学类", "07"), "0705": ("地理科学类", "07"),
    "0706": ("大气科学类", "07"), "0707": ("海洋科学类", "07"),
    "0708": ("地球物理学类", "07"), "0709": ("地质学类", "07"),
    "0710": ("生物科学类", "07"), "0711": ("心理学类", "07"),
    "0712": ("统计学类", "07"), "0801": ("力学类", "08"),
    "0802": ("机械类", "08"), "0803": ("仪器类", "08"),
    "0804": ("材料类", "08"), "0805": ("能源动力类", "08"),
    "0806": ("电气类", "08"), "0807": ("电子信息类", "08"),
    "0808": ("自动化类", "08"), "0809": ("计算机类", "08"),
    "0810": ("土木类", "08"), "0811": ("水利类", "08"),
    "0812": ("测绘类", "08"), "0813": ("化工与制药类", "08"),
    "0814": ("地质类", "08"), "0815": ("矿业类", "08"),
    "0816": ("纺织类", "08"), "0817": ("轻工类", "08"),
    "0818": ("交通运输类", "08"), "0819": ("海洋工程类", "08"),
    "0820": ("航空航天类", "08"), "0821": ("兵器类", "08"),
    "0822": ("核工程类", "08"), "0823": ("农业工程类", "08"),
    "0824": ("林业工程类", "08"), "0825": ("环境科学与工程类", "08"),
    "0826": ("生物医学工程类", "08"), "0827": ("食品科学与工程类", "08"),
    "0828": ("建筑类", "08"), "0829": ("安全科学与工程类", "08"),
    "0830": ("生物工程类", "08"), "0831": ("公安技术类", "08"),
    "0901": ("植物生产类", "09"), "0902": ("自然保护与环境生态类", "09"),
    "0903": ("动物生产类", "09"), "0904": ("动物医学类", "09"),
    "0905": ("林学类", "09"), "0906": ("水产类", "09"),
    "0907": ("草学类", "09"), "1001": ("基础医学类", "10"),
    "1002": ("临床医学类", "10"), "1003": ("口腔医学类", "10"),
    "1004": ("公共卫生与预防医学类", "10"), "1005": ("中医学类", "10"),
    "1006": ("中西医结合类", "10"), "1007": ("药学类", "10"),
    "1008": ("中药学类", "10"), "1009": ("法医学类", "10"),
    "1010": ("医学技术类", "10"), "1011": ("护理学类", "10"),
    "1201": ("管理科学与工程类", "12"), "1202": ("工商管理类", "12"),
    "1203": ("农业经济管理类", "12"), "1204": ("公共管理类", "12"),
    "1205": ("图书情报与档案管理类", "12"), "1206": ("物流管理与工程类", "12"),
    "1207": ("工业工程类", "12"), "1208": ("电子商务类", "12"),
    "1209": ("旅游管理类", "12"), "1301": ("艺术学理论类", "13"),
    "1302": ("音乐与舞蹈学类", "13"), "1303": ("戏剧与影视学类", "13"),
    "1304": ("美术学类", "13"), "1305": ("设计学类", "13"),
}

# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class MajorRecord:
    """专业数据记录 — 字段与 base.majors 表对齐"""
    major_id: str = ""
    name: str = ""
    name_full: Optional[str] = None
    category_id: Optional[str] = None
    subject_group: Optional[str] = None
    subject_group_3p3: Optional[str] = None
    level: str = "本科"
    study_years: int = 4
    degree: Optional[str] = None
    description: Optional[str] = None
    main_courses: Optional[List[str]] = None
    typical_schools: Optional[int] = None
    employment_rate: Optional[float] = None
    employment_direction: Optional[str] = None
    salary_avg: Optional[float] = None
    is_special: bool = False
    special_label: Optional[str] = None
    version_year: int = 2024
    data_source: str = "教育部专业目录"
    data_version: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class MajorCategoryRecord:
    """学科门类数据记录 — 字段与 base.major_categories 表对齐"""
    category_id: Optional[int] = None
    category_name: str = ""
    category_code: str = ""
    level: str = "本科"
    parent_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


# ============================================================================
# 内置专业目录数据
# 格式: "专业代码|专业名称|修业年限|学位名称" 每行一条
# 后缀: K=国家控制布点, T=特设专业, TK=国家控制布点+特设
# ============================================================================

# --- 本科专业数据 (2024年版, 约816条) ---
_UG = {}
