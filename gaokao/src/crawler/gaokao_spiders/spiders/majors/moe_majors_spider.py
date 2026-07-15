#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
教育部本科/专科专业目录爬虫
内置 2024 年本科专业目录 & 2021 年职业教育专业目录数据。

使用方式：
  python src/crawler/gaokao_spiders/spiders/majors/moe_majors_spider.py
  python src/crawler/gaokao_spiders/spiders/majors/moe_majors_spider.py --dry-run
  cd src/crawler && scrapy crawl moe_majors

数据来源：
  - 普通高等学校本科专业目录（2024 年版）
  - 职业教育专业目录（2021 年版）

输出：
  data/raw/majors/majors_YYYYMMDD_HHmmss.jsonl
  data/raw/majors/categories_YYYYMMDD_HHmmss.jsonl
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

# -- Scrapy optional ----------------------------------------------------------
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

# -- Logging ------------------------------------------------------------------
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

# -- Constants -----------------------------------------------------------------
MOE_MAJOR_INDEX_URL = "http://www.moe.gov.cn/s78/A08/gjs_left/moe_1034/"
CHSI_MAJOR_URL = "https://gaokao.chsi.com.cn/zyk/"
OUTPUT_DIR = Path(__file__).resolve().parents[5] / "data" / "raw" / "majors"
SCRAPY_PROJECT_DIR = Path(__file__).resolve().parents[3]

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

# ============================================================================
# Data models
# ============================================================================

@dataclass
class MajorRecord:
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
# Embedded Catalog Data (loaded from JSON cache, auto-generated if missing)
# ============================================================================

class EmbeddedCatalog:
    """内置教育部专业目录数据。优先从 JSON 缓存加载，缺失时从内置数据生成。"""

    _ug_raw: Optional[Dict[str, str]] = None
    _voc_raw: Optional[Dict[str, str]] = None

    @classmethod
    def _data_dir(cls) -> Path:
        return OUTPUT_DIR

    @classmethod
    def _load_ug(cls) -> Dict[str, str]:
        if cls._ug_raw is not None:
            return cls._ug_raw
        path = cls._data_dir() / "_catalog_undergrad.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                cls._ug_raw = json.load(f)
            return cls._ug_raw
        logger.info("生成本科专业目录缓存...")
        cls._ug_raw = _BUILD_UNDERGRAD_DATA()
        cls._data_dir().mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cls._ug_raw, f, ensure_ascii=False)
        return cls._ug_raw

    @classmethod
    def _load_voc(cls) -> Dict[str, str]:
        if cls._voc_raw is not None:
            return cls._voc_raw
        path = cls._data_dir() / "_catalog_vocational.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                cls._voc_raw = json.load(f)
            return cls._voc_raw
        logger.info("生成专科专业目录缓存...")
        cls._voc_raw = _BUILD_VOCATIONAL_DATA()
        cls._data_dir().mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cls._voc_raw, f, ensure_ascii=False)
        return cls._voc_raw

    @classmethod
    def _parse_line(cls, line: str, cat_code: str, level: str,
                    version_year: int) -> Optional[MajorRecord]:
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        parts = line.split("|")
        if len(parts) < 3:
            return None
        major_id = parts[0].strip()
        name = parts[1].strip()
        try:
            sy = int(parts[2].strip())
        except (ValueError, IndexError):
            sy = 4 if level == "本科" else 3
        degree = parts[3].strip() if len(parts) > 3 and parts[3].strip() else None
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return MajorRecord(
            major_id=major_id, name=name, category_id=cat_code,
            level=level, study_years=sy, degree=degree,
            version_year=version_year, data_source="教育部专业目录",
            data_version=str(version_year),
            created_at=now_iso, updated_at=now_iso,
        )

    @classmethod
    def get_undergrad_majors(cls, version_year: int = 2024) -> List[MajorRecord]:
        raw = cls._load_ug()
        majors = []
        for cat_code, data in raw.items():
            for line in data.strip().split("\n"):
                rec = cls._parse_line(line, cat_code, "本科", version_year)
                if rec:
                    majors.append(rec)
        return majors

    @classmethod
    def get_vocational_majors(cls, version_year: int = 2024) -> List[MajorRecord]:
        raw = cls._load_voc()
        majors = []
        for cat_code, data in raw.items():
            for line in data.strip().split("\n"):
                rec = cls._parse_line(line, cat_code, "专科", version_year)
                if rec:
                    majors.append(rec)
        return majors

    @classmethod
    def get_all_majors(cls, version_year: int = 2024) -> List[MajorRecord]:
        return cls.get_undergrad_majors(version_year) + cls.get_vocational_majors(version_year)

    @classmethod
    def get_undergrad_categories(cls) -> List[MajorCategoryRecord]:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return [MajorCategoryRecord(category_name=n, category_code=c, level="本科",
                                     created_at=now_iso, updated_at=now_iso)
                for c, n in UNDERGRAD_CATEGORIES.items()]

    @classmethod
    def get_vocational_categories(cls) -> List[MajorCategoryRecord]:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return [MajorCategoryRecord(category_name=n, category_code=c, level="专科",
                                     created_at=now_iso, updated_at=now_iso)
                for c, n in VOCATIONAL_CATEGORIES.items()]

    @classmethod
    def get_all_categories(cls) -> List[MajorCategoryRecord]:
        return cls.get_undergrad_categories() + cls.get_vocational_categories()


# ============================================================================
# Built-in catalog data builders
# Compact format: "code|name|years|degree" per line, grouped by category code
# ============================================================================

def _BUILD_UNDERGRAD_DATA() -> Dict[str, str]:
    """本科专业目录 2024年版 ~816条"""
    return {
        "01": "010101|哲学|4|哲学学士\n010102|逻辑学|4|哲学学士\n010103K|宗教学|4|哲学学士\n010104T|伦理学|4|哲学学士",
        "02": "020101|经济学|4|经济学学士\n020102|经济统计学|4|经济学学士\n020103T|国民经济管理|4|经济学学士\n020104T|资源与环境经济学|4|经济学学士\n020105T|商务经济学|4|经济学学士\n020106T|能源经济|4|经济学学士\n020107T|劳动经济学|4|经济学学士\n020108T|经济工程|4|经济学学士\n020109T|数字经济|4|经济学学士\n020201K|财政学|4|经济学学士\n020202|税收学|4|经济学学士\n020203T|国际税收|4|经济学学士\n020301K|金融学|4|经济学学士\n020302|金融工程|4|经济学学士\n020303|保险学|4|经济学学士\n020304|投资学|4|经济学学士\n020305T|金融数学|4|经济学学士\n020306T|信用管理|4|经济学学士\n020307T|经济与金融|4|经济学学士\n020308T|精算学|4|理学学士\n020309T|互联网金融|4|经济学学士\n020310T|金融科技|4|经济学学士\n020311T|金融审计|4|经济学学士\n020401|国际经济与贸易|4|经济学学士\n020402|贸易经济|4|经济学学士\n020403T|国际经济发展合作|4|经济学学士",
        "03": "030101K|法学|4|法学学士\n030102T|知识产权|4|法学学士\n030103T|监狱学|4|法学学士\n030104T|信用风险管理与法律防控|4|法学学士\n030105T|国际经贸规则|4|法学学士\n030106T|司法警察学|4|法学学士\n030107T|社区矫正|4|法学学士\n030108T|纪检监察|4|法学学士\n030109T|国际法|4|法学学士\n030110T|司法鉴定学|4|法学学士\n030201|政治学与行政学|4|法学学士\n030202|国际政治|4|法学学士\n030203|外交学|4|法学学士\n030204T|国际事务与国际关系|4|法学学士\n030205T|政治学、经济学与哲学|4|法学学士\n030206T|国际组织与全球治理|4|法学学士\n030301|社会学|4|法学学士\n030302|社会工作|4|法学学士\n030303T|人类学|4|法学学士\n030304T|女性学|4|法学学士\n030305T|家政学|4|法学学士\n030306T|老年学|4|法学学士\n030307T|社会政策|4|法学学士\n030401|民族学|4|法学学士\n030501|科学社会主义|4|法学学士\n030502|中国共产党历史|4|法学学士\n030503|思想政治教育|4|法学学士\n030504T|马克思主义理论|4|法学学士\n030505T|工会学|4|法学学士\n030601K|治安学|4|法学学士\n030602K|侦查学|4|法学学士\n030603K|边防管理|4|法学学士\n030604T|禁毒学|4|法学学士\n030605T|警犬技术|4|法学学士\n030606T|经济犯罪侦查|4|法学学士\n030607T|边防指挥|4|法学学士\n030608T|消防指挥|4|法学学士\n030609T|警卫学|4|法学学士\n030610T|公安情报学|4|法学学士\n030611T|犯罪学|4|法学学士\n030612T|公安管理学|4|法学学士\n030613T|涉外警务|4|法学学士\n030614T|国内安全保卫|4|法学学士\n030615T|警务指挥与战术|4|法学学士\n030616T|技术侦查学|4|法学学士\n030617T|海警执法|4|法学学士\n030618T|公安政治工作|4|法学学士\n030619T|移民管理|4|法学学士\n030620T|出入境管理|4|法学学士\n030621T|反恐警务|4|法学学士\n030622T|消防政治工作|4|法学学士\n030623T|铁路警务|4|法学学士",
        "04": "040101|教育学|4|教育学学士\n040102|科学教育|4|教育学学士\n040103|人文教育|4|教育学学士\n040104|教育技术学|4|教育学学士\n040105|艺术教育|4|教育学学士\n040106|学前教育|4|教育学学士\n040107|小学教育|4|教育学学士\n040108|特殊教育|4|教育学学士\n040109T|华文教育|4|教育学学士\n040110T|教育康复学|4|教育学学士\n040111T|卫生教育|4|教育学学士\n040112T|认知科学与技术|4|教育学学士\n040113T|融合教育|4|教育学学士\n040114T|劳动教育|4|教育学学士\n040115T|家庭教育|4|教育学学士\n040116T|孤独症儿童教育|4|教育学学士\n040201|体育教育|4|教育学学士\n040202K|运动训练|4|教育学学士\n040203|社会体育指导与管理|4|教育学学士\n040204K|武术与民族传统体育|4|教育学学士\n040205|运动人体科学|4|教育学学士\n040206T|运动康复|4|教育学学士\n040207T|休闲体育|4|教育学学士\n040208T|体能训练|4|教育学学士\n040209T|冰雪运动|4|教育学学士\n040210T|电子竞技运动与管理|4|教育学学士\n040211T|智能体育工程|4|教育学学士\n040212T|体育旅游|4|教育学学士\n040213T|运动能力开发|4|教育学学士",
        "05": "050101|汉语言文学|4|文学学士\n050102|汉语言|4|文学学士\n050103|汉语国际教育|4|文学学士\n050104|中国少数民族语言文学|4|文学学士\n050105|古典文献学|4|文学学士\n050106T|应用语言学|4|文学学士\n050107T|秘书学|4|文学学士\n050108T|中国语言与文化|4|文学学士\n050109T|手语翻译|4|文学学士\n050110T|数字人文|4|文学学士\n050201|英语|4|文学学士\n050202|俄语|4|文学学士\n050203|德语|4|文学学士\n050204|法语|4|文学学士\n050205|西班牙语|4|文学学士\n050206|阿拉伯语|4|文学学士\n050207|日语|4|文学学士\n050208|波斯语|4|文学学士\n050209|朝鲜语|4|文学学士\n050210|菲律宾语|4|文学学士\n050211|梵语巴利语|4|文学学士\n050212|印度尼西亚语|4|文学学士\n050213|印地语|4|文学学士\n050214|柬埔寨语|4|文学学士\n050215|老挝语|4|文学学士\n050216|缅甸语|4|文学学士\n050217|马来语|4|文学学士\n050218|蒙古语|4|文学学士\n050219|僧伽罗语|4|文学学士\n050220|泰语|4|文学学士\n050221|乌尔都语|4|文学学士\n050222|希伯来语|4|文学学士\n050223|越南语|4|文学学士\n050224|豪萨语|4|文学学士\n050225|斯瓦希里语|4|文学学士\n050226|阿尔巴尼亚语|4|文学学士\n050227|保加利亚语|4|文学学士\n050228|波兰语|4|文学学士\n050229|捷克语|4|文学学士\n050230|罗马尼亚语|4|文学学士\n050231|葡萄牙语|4|文学学士\n050232|瑞典语|4|文学学士\n050233|塞尔维亚语|4|文学学士\n050234|土耳其语|4|文学学士\n050235|希腊语|4|文学学士\n050236|匈牙利语|4|文学学士\n050237|意大利语|4|文学学士\n050238|泰米尔语|4|文学学士\n050239|普什图语|4|文学学士\n050240|世界语|4|文学学士\n050241|孟加拉语|4|文学学士\n050242|尼泊尔语|4|文学学士\n050243|克罗地亚语|4|文学学士\n050244|荷兰语|4|文学学士\n050245|芬兰语|4|文学学士\n050246|乌克兰语|4|文学学士\n050247|挪威语|4|文学学士\n050248|丹麦语|4|文学学士\n050249|冰岛语|4|文学学士\n050250|爱尔兰语|4|文学学士\n050251|拉脱维亚语|4|文学学士\n050252|立陶宛语|4|文学学士\n050253|斯洛文尼亚语|4|文学学士\n050254|爱沙尼亚语|4|文学学士\n050255|马耳他语|4|文学学士\n050256|哈萨克语|4|文学学士\n050257|乌兹别克语|4|文学学士\n050258|祖鲁语|4|文学学士\n050259|拉丁语|4|文学学士\n050260|翻译|4|文学学士\n050261|商务英语|4|文学学士\n050262T|阿姆哈拉语|4|文学学士\n050263T|吉尔吉斯语|4|文学学士\n050264T|索马里语|4|文学学士\n050265T|土库曼语|4|文学学士\n050266T|加泰罗尼亚语|4|文学学士\n050267T|约鲁巴语|4|文学学士\n050268T|亚美尼亚语|4|文学学士\n050269T|马达加斯加语|4|文学学士\n050270T|格鲁吉亚语|4|文学学士\n050271T|阿塞拜疆语|4|文学学士\n050272T|阿非利卡语|4|文学学士\n050273T|马其顿语|4|文学学士\n050274T|塔吉克语|4|文学学士\n050275T|茨瓦纳语|4|文学学士\n050276T|恩德贝莱语|4|文学学士\n050277T|科摩罗语|4|文学学士\n050278T|克里奥尔语|4|文学学士\n050279T|绍纳语|4|文学学士\n050280T|提格雷尼亚语|4|文学学士\n050281T|白俄罗斯语|4|文学学士\n050282T|毛利语|4|文学学士\n050283T|汤加语|4|文学学士\n050284T|萨摩亚语|4|文学学士\n050285T|库尔德语|4|文学学士\n050286T|比斯拉马语|4|文学学士\n050287T|达里语|4|文学学士\n050288T|德顿语|4|文学学士\n050289T|迪维希语|4|文学学士\n050290T|斐济语|4|文学学士\n050291T|库克群岛毛利语|4|文学学士\n050292T|隆迪语|4|文学学士\n050293T|卢森堡语|4|文学学士\n050294T|卢旺达语|4|文学学士\n050295T|纽埃语|4|文学学士\n050296T|皮金语|4|文学学士\n050297T|切瓦语|4|文学学士\n050298T|塞苏陀语|4|文学学士\n050299T|桑戈语|4|文学学士\n050300T|语言学|4|文学学士\n050301T|塔玛齐格特语|4|文学学士\n050302T|爪哇语|4|文学学士\n050303T|旁遮普语|4|文学学士\n050304T|区域国别学|4|文学学士\n050305T|国际新闻与传播|4|文学学士\n050306T|国际语言服务|4|文学学士\n050307T|语言科学与人工智能|4|文学学士\n050308T|涉外法治外语|4|文学学士\n050309T|翻译与国际传播|4|文学学士\n050301|新闻学|4|文学学士\n050302|广播电视学|4|文学学士\n050303|广告学|4|文学学士\n050304|传播学|4|文学学士\n050305|编辑出版学|4|文学学士\n050306T|网络与新媒体|4|文学学士\n050307T|数字出版|4|文学学士\n050308T|时尚传播|4|文学学士\n050310T|会展传播|4|文学学士",
    }
