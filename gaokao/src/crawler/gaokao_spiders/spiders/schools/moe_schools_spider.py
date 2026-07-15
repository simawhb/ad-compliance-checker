#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
教育部全国高等学校名单爬虫

功能：
  1. 从教育部官网搜索并下载最新全国高等学校名单
  2. 解析 PDF 或 Excel 格式文件
  3. 提取结构化院校数据，输出 JSON Lines

使用方式：
  # 直接运行（自动搜索最新名单）
  python src/crawler/gaokao_spiders/spiders/schools/moe_schools_spider.py

  # 手动指定文件
  python src/crawler/gaokao_spiders/spiders/schools/moe_schools_spider.py --input /path/to/list.xlsx

  # 预览模式（只输出前5条）
  python src/crawler/gaokao_spiders/spiders/schools/moe_schools_spider.py --dry-run

  # Scrapy 方式
  cd src/crawler && scrapy crawl moe_schools

数据来源：
  教育部全国高等学校名单
  http://www.moe.gov.cn/jyb_xxgk/s5743/s5744/

输出：
  data/raw/schools/raw_YYYYMMDD_HHmmss.jsonl
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
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# 可选依赖 — 按需导入，缺失时给出明确提示
# ---------------------------------------------------------------------------

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import xlrd
    HAS_XLRD = True
except ImportError:
    HAS_XLRD = False

# ---------------------------------------------------------------------------
# Scrapy 可选导入 — 直接运行模式不需要 scrapy
# ---------------------------------------------------------------------------

HAS_SCRAPY = False
CrawlerProcess = None
_SpiderBase = object  # type: ignore  # 回退基类

try:
    import scrapy  # noqa: F811
    from scrapy.crawler import CrawlerProcess  # noqa: F811

    _SpiderBase = scrapy.Spider  # type: ignore[assignment]
    HAS_SCRAPY = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# 日志配置
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
            LOG_DIR / f"moe_schools_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("moe_schools")

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 教育部高校名单索引页
MOE_LIST_INDEX_URL = "http://www.moe.gov.cn/jyb_xxgk/s5743/s5744/"

# 常见的高校名单发布 URL 模式（按年份）
KNOWN_URLS: List[str] = [
    "http://www.moe.gov.cn/jyb_xxgk/s5743/s5744/202406/t20240620_1135877.html",
    "http://www.moe.gov.cn/jyb_xxgk/s5743/s5744/202306/t20230619_1064976.html",
    "http://www.moe.gov.cn/jyb_xxgk/s5743/s5744/202206/t20220617_638319.html",
]

# 省份名称集合（用于从"所在地"字段中提取省份和城市）
PROVINCE_NAMES: List[str] = [
    "北京市", "天津市", "上海市", "重庆市",
    "河北省", "山西省", "辽宁省", "吉林省", "黑龙江省",
    "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省", "广东省", "海南省",
    "四川省", "贵州省", "云南省", "陕西省", "甘肃省", "青海省",
    "台湾省",
    "内蒙古自治区", "广西壮族自治区", "西藏自治区",
    "宁夏回族自治区", "新疆维吾尔自治区",
    "香港特别行政区", "澳门特别行政区",
]

# 省级行政区简称 → 全称映射
PROVINCE_SHORT_MAP: Dict[str, str] = {
    "北京": "北京市", "天津": "天津市", "上海": "上海市", "重庆": "重庆市",
    "河北": "河北省", "山西": "山西省", "辽宁": "辽宁省", "吉林": "吉林省",
    "黑龙江": "黑龙江省", "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
    "福建": "福建省", "江西": "江西省", "山东": "山东省", "河南": "河南省",
    "湖北": "湖北省", "湖南": "湖南省", "广东": "广东省", "海南": "海南省",
    "四川": "四川省", "贵州": "贵州省", "云南": "云南省", "陕西": "陕西省",
    "甘肃": "甘肃省", "青海": "青海省", "台湾": "台湾省",
    "内蒙古": "内蒙古自治区", "广西": "广西壮族自治区",
    "西藏": "西藏自治区", "宁夏": "宁夏回族自治区",
    "新疆": "新疆维吾尔自治区",
    "香港": "香港特别行政区", "澳门": "澳门特别行政区",
}

# 办学类型关键词映射（从院校名称推断）
TYPE_KEYWORDS: List[tuple] = [
    (["理工大学", "理工学院", "工业"], "理工"),
    (["师范大学", "师范学院", "师范高等"], "师范"),
    (["农业大学", "农业学院", "林业大学", "林业学院", "农林"], "农林"),
    (["医科大学", "医学院", "中医药大学", "中医学院", "药科大学"], "医药"),
    (["财经大学", "财经学院", "金融学院", "经济学院", "商学院"], "财经"),
    (["政法大学", "政法学院", "政治学院"], "政法"),
    (["体育大学", "体育学院"], "体育"),
    (["艺术学院", "美术学院", "音乐学院", "戏剧学院", "电影学院", "舞蹈学院"], "艺术"),
    (["民族大学", "民族学院"], "民族"),
    (["外国语大学", "外国语学院", "语言大学", "语文学院"], "语言"),
    (["军事", "国防", "海军", "空军", "陆军", "武警", "火箭军", "战略支援"], "军事"),
]

# 已知的直辖市（所在地只到市/区级，城市等于省份）
DIRECT_MUNICIPALITIES = {"北京市", "天津市", "上海市", "重庆市"}

# 默认输出目录
OUTPUT_DIR = Path(__file__).resolve().parents[5] / "data" / "raw" / "schools"

# Scrapy 项目路径（用于 Scrapy 模式）
SCRAPY_PROJECT_DIR = Path(__file__).resolve().parents[3]


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class SchoolRecord:
    """院校数据记录，字段与 base.schools 表对齐"""

    # === 核心标识 ===
    code_edu: str = ""                     # 教育部院校代码（5位数字字符串，主键）
    name: str = ""                         # 院校全称

    # === 基本信息 ===
    name_aliases: List[str] = field(default_factory=list)   # 曾用名/别名
    name_en: Optional[str] = None          # 英文名称
    code_gaokao: Optional[Dict] = None     # 高考院校代码（JSON按省份）
    code_yb: Optional[str] = None          # 研招网代码
    level: Optional[str] = None            # 办学层次（本科/专科/职业本科）
    type: Optional[str] = None             # 办学类型
    category: Optional[str] = None         # 院校类别
    is_211: bool = False                   # 是否211
    is_985: bool = False                   # 是否985
    is_double_first_class: bool = False    # 是否双一流
    double_first_class_round: Optional[int] = None  # 双一流批次
    admin_department: Optional[str] = None  # 主管部门

    # === 地理位置 ===
    province: Optional[str] = None         # 所在省份
    city: Optional[str] = None             # 所在城市
    district: Optional[str] = None         # 所在区县
    address: Optional[str] = None          # 详细地址
    postal_code: Optional[str] = None      # 邮政编码

    # === 联系方式 ===
    website: Optional[str] = None          # 官网URL
    admission_office_phone: Optional[str] = None  # 招生办电话
    admission_office_website: Optional[str] = None  # 招生网URL
    email: Optional[str] = None            # 招生邮箱

    # === 媒体资源 ===
    logo_url: Optional[str] = None         # 校徽URL
    thumbnail_url: Optional[str] = None    # 校门图片URL

    # === 院校概况 ===
    established_year: Optional[int] = None # 建校年份
    history: Optional[str] = None          # 校史简介
    area_acre: Optional[float] = None      # 占地面积（亩）
    student_undergrad: Optional[int] = None  # 本科生人数
    student_postgrad: Optional[int] = None   # 研究生人数
    student_total: Optional[int] = None    # 在校生总数
    faculty_count: Optional[int] = None    # 教职工总数
    faculty_professor: Optional[int] = None  # 教授人数
    library_volume: Optional[float] = None # 图书馆藏书量（万册）

    # === 校区信息 ===
    campus_count: Optional[int] = None     # 校区数量
    campus_info: Optional[Dict] = None     # 校区信息（JSON）

    # === 学术实力 ===
    academician_count: Optional[int] = None  # 两院院士人数
    doctoral_programs: Optional[int] = None  # 博士点数量
    master_programs: Optional[int] = None    # 硕士点数量
    key_labs: Optional[List] = None          # 国家重点实验室
    features: Optional[List] = None          # 办学特色标签

    # === 费用信息 ===
    scholarship_info: Optional[str] = None   # 奖助学金信息
    tuition_range: Optional[Dict] = None     # 学费范围（JSON）
    accommodation: Optional[str] = None      # 住宿条件描述
    accommodation_fee: Optional[str] = None  # 住宿费范围

    # === 元数据 ===
    data_source: str = "教育部全国高等学校名单"
    data_version: Optional[str] = None     # 数据版本/年份
    created_at: Optional[str] = None       # ISO 8601 时间戳
    updated_at: Optional[str] = None       # ISO 8601 时间戳

    def to_dict(self) -> Dict[str, Any]:
        """转为字典，保留 None 值以在 JSON 中输出 null"""
        return asdict(self)

    def to_jsonl_line(self) -> str:
        """转为 JSON Lines 单行"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


# ============================================================================
# 解析引擎
# ============================================================================

class MOESchoolsParser:
    """
    教育部高校名单解析器。

    支持格式：
      - Excel (.xlsx / .xls)
      - PDF (.pdf) — 表格型 PDF

    解析流程：
      1. 读取文件 → 定位数据表
      2. 识别列头 → 提取各列
      3. 逐行清洗 → 生成 SchoolRecord
    """

    # 常见的列名模式（教育部名单）
    COLUMN_PATTERNS = {
        "code_edu": [
            "院校代码", "学校代码", "学校标识码", "高等学校代码",
            "代码", "院校标识码", "高校代码",
        ],
        "name": [
            "学校名称", "院校名称", "高校名称", "名称", "学校", "院校",
        ],
        "admin_department": [
            "主管部门", "举办者", "主管", "管理部门", "所属部门",
        ],
        "location": [
            "所在地", "所在地区", "地区", "省份", "所在省市", "所在省",
            "院校所在地", "学校所在地",
        ],
        "level": [
            "办学层次", "层次", "学历层次", "学校类型",
        ],
        "remark": [
            "备注", "说明", "注",
        ],
    }

    def __init__(self):
        self.errors: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 入口
    # ------------------------------------------------------------------

    def parse(self, file_path: str, year: Optional[str] = None) -> List[SchoolRecord]:
        """
        解析高校名单文件，返回 SchoolRecord 列表。

        参数:
            file_path: PDF 或 Excel 文件路径
            year: 数据年份（如 "2024"），若为 None 则尝试从文件名提取

        返回:
            SchoolRecord 列表
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if year is None:
            year = self._extract_year_from_filename(file_path.name)

        suffix = file_path.suffix.lower()

        if suffix in (".xlsx", ".xls"):
            if not HAS_OPENPYXL:
                raise ImportError(
                    "解析 Excel 需要 openpyxl 库，请运行: pip install openpyxl"
                )
            rows = self._parse_excel(file_path)
        elif suffix == ".pdf":
            if not HAS_PDFPLUMBER:
                raise ImportError(
                    "解析 PDF 需要 pdfplumber 库，请运行: pip install pdfplumber"
                )
            rows = self._parse_pdf(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {suffix}（仅支持 .xlsx/.xls/.pdf）")

        records = []
        for row_idx, raw_row in enumerate(rows):
            try:
                record = self._build_record(raw_row, year)
                if record:
                    records.append(record)
            except Exception as exc:
                logger.warning("第 %d 行解析失败: %s", row_idx + 1, exc)
                self.errors.append({
                    "row_index": row_idx,
                    "raw_data": raw_row,
                    "error": str(exc),
                })

        logger.info(
            "解析完成: 共 %d 行, 成功 %d 条, 失败 %d 条",
            len(rows), len(records), len(self.errors),
        )
        return records

    # ------------------------------------------------------------------
    # 列识别
    # ------------------------------------------------------------------

    def _identify_columns(self, headers: List[str]) -> Dict[str, int]:
        """
        自动识别列名对应的列索引。

        返回:
            {"code_edu": col_idx, "name": col_idx, ...}
        """
        mapping: Dict[str, int] = {}

        for idx, header in enumerate(headers):
            if not header or not isinstance(header, str):
                continue
            header_clean = header.strip().replace("\n", "").replace("\r", "")

            for field, patterns in self.COLUMN_PATTERNS.items():
                if field in mapping:
                    continue  # 已匹配的字段不再重复匹配
                for pattern in patterns:
                    if pattern in header_clean:
                        mapping[field] = idx
                        break

        return mapping

    # ------------------------------------------------------------------
    # Excel 解析
    # ------------------------------------------------------------------

    def _parse_excel(self, file_path: Path) -> List[Dict[str, Any]]:
        """解析 Excel 文件，返回原始行列表"""
        # 优先 openpyxl（支持 .xlsx），fallback 到 xlrd（支持 .xls）
        ext = file_path.suffix.lower()
        if ext == ".xls" and HAS_XLRD:
            return self._parse_excel_xlrd(file_path)
        if ext == ".xlsx" or HAS_OPENPYXL:
            pass  # 继续用 openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)

        # 优先使用第一个 sheet
        ws = wb.worksheets[0]
        logger.info("Excel 文件: %s, sheet: %s", file_path.name, ws.title)

        # 读取所有行
        all_rows: List[List] = []
        for row in ws.iter_rows(min_row=1, values_only=True):
            all_rows.append([cell if cell is not None else "" for cell in row])

        wb.close()

        if not all_rows:
            logger.warning("Excel 文件为空")
            return []

        # 定位表头行 — 查找含有关键列名的行
        header_row_idx = self._find_header_row(all_rows)
        if header_row_idx is None:
            logger.error("无法定位表头行，请检查文件格式")
            return []

        headers = [str(c).strip() for c in all_rows[header_row_idx]]
        col_map = self._identify_columns(headers)
        logger.info("表头行 %d, 识别到列: %s", header_row_idx + 1, col_map)

        # 提取数据行
        rows = []
        for row_idx in range(header_row_idx + 1, len(all_rows)):
            row = all_rows[row_idx]
            if self._is_empty_row(row):
                continue

            parsed: Dict[str, Any] = {}
            for field, col_idx in col_map.items():
                if col_idx < len(row):
                    val = row[col_idx]
                    if isinstance(val, str):
                        val = val.strip()
                    parsed[field] = val
                else:
                    parsed[field] = ""

            # 也存入原始所有列值供调试
            parsed["_raw_cells"] = [str(c).strip() for c in row]

            # 跳过表头重复行
            if parsed.get("name") and str(parsed["name"]) in (
                "学校名称", "院校名称", "高校名称", "名称"
            ):
                continue

            rows.append(parsed)

        return rows

    def _parse_excel_xlrd(self, file_path: Path) -> List[Dict[str, Any]]:
        """用 xlrd 解析旧版 .xls 文件"""
        wb = xlrd.open_workbook(str(file_path))
        ws = wb.sheet_by_index(0)
        logger.info("Excel(.xls) 文件: %s, sheet: %s", file_path.name, ws.name)

        all_rows: List[List] = []
        for row_idx in range(ws.nrows):
            row = [str(ws.cell_value(row_idx, c)).strip() if ws.cell_type(row_idx, c) else "" for c in range(ws.ncols)]
            all_rows.append(row)

        # 定位表头行
        # 复用相同的查找逻辑
        header_row_idx = self._find_header_row(all_rows)
        if header_row_idx is None:
            logger.error("无法定位表头行，请检查文件格式")
            return []

        headers = [str(c).strip() for c in all_rows[header_row_idx]]
        col_map = self._identify_columns(headers)
        logger.info("表头行 %d, 识别到列: %s", header_row_idx + 1, col_map)

        rows = []
        for row_idx in range(header_row_idx + 1, ws.nrows):
            row_vals = all_rows[row_idx]
            if self._is_empty_row(row_vals):
                continue

            parsed: Dict[str, Any] = {}
            for field, col_idx in col_map.items():
                if col_idx < len(row_vals):
                    parsed[field] = row_vals[col_idx]
                else:
                    parsed[field] = ""

            parsed["_raw_cells"] = row_vals

            if parsed.get("name") and str(parsed["name"]) in (
                "学校名称", "院校名称", "高校名称", "名称"
            ):
                continue

            rows.append(parsed)

        wb.release_resources()
        return rows

    # ------------------------------------------------------------------
    # PDF 解析
    # ------------------------------------------------------------------

    def _parse_pdf(self, file_path: Path) -> List[Dict[str, Any]]:
        """解析 PDF 文件，提取表格数据"""
        logger.info("PDF 文件: %s", file_path.name)

        all_tables: List[List[List]] = []

        with pdfplumber.open(file_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for table_idx, table in enumerate(tables):
                    if table:
                        cleaned = self._clean_pdf_table(table)
                        if cleaned:
                            all_tables.append(cleaned)
                        logger.debug(
                            "PDF 第 %d 页, table %d: %d 行",
                            page_idx + 1, table_idx + 1, len(cleaned),
                        )

        if not all_tables:
            logger.error("PDF 中未找到表格数据")
            return []

        # 找包含最多数据的表格（通常就是主体高校名单表）
        best_table = max(all_tables, key=len)

        if not best_table:
            return []

        # 定位表头
        header_row_idx = self._find_header_row(best_table)
        if header_row_idx is None:
            logger.error("PDF 表格中无法定位表头行")
            return []

        headers = [str(c).strip() if c else "" for c in best_table[header_row_idx]]
        col_map = self._identify_columns(headers)
        logger.info("PDF 表头行 %d, 识别到列: %s", header_row_idx + 1, col_map)

        # 提取数据行
        rows = []
        for row_idx in range(header_row_idx + 1, len(best_table)):
            row = best_table[row_idx]
            if self._is_empty_row(row):
                continue

            parsed: Dict[str, Any] = {}
            for field, col_idx in col_map.items():
                if col_idx < len(row):
                    val = row[col_idx]
                    if isinstance(val, str):
                        val = val.strip()
                    elif val is None:
                        val = ""
                    parsed[field] = val
                else:
                    parsed[field] = ""

            parsed["_raw_cells"] = [str(c).strip() if c else "" for c in row]

            # 跳过表头重复行
            if parsed.get("name") in (
                "学校名称", "院校名称", "高校名称", "名称"
            ):
                continue

            rows.append(parsed)

        return rows

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _find_header_row(self, rows: List[List]) -> Optional[int]:
        """在行列表中查找表头行（包含"学校名称"等关键列名的行）"""
        for idx, row in enumerate(rows):
            row_text = " ".join(str(c) for c in row if c)
            if "学校名称" in row_text or "院校名称" in row_text:
                return idx
        # 降级：查找含"名称"的行
        for idx, row in enumerate(rows):
            row_text = " ".join(str(c) for c in row if c)
            if "名称" in row_text and ("代码" in row_text or "层次" in row_text):
                return idx
        return None

    @staticmethod
    def _is_empty_row(row: List) -> bool:
        """判断行是否为空"""
        if not row:
            return True
        return all(
            c is None or (isinstance(c, str) and c.strip() == "") or c == ""
            for c in row
        )

    @staticmethod
    def _clean_pdf_table(table: List[List]) -> List[List]:
        """清洗 PDF 表格：合并多行单元格、去除完全空行"""
        cleaned = []
        for row in table:
            if row is None:
                continue
            cleaned_row = [
                cell.strip() if isinstance(cell, str) else (cell if cell else "")
                for cell in row
            ]
            if not all(c == "" or c is None for c in cleaned_row):
                cleaned.append(cleaned_row)
        return cleaned

    @staticmethod
    def _extract_year_from_filename(filename: str) -> Optional[str]:
        """从文件名中提取年份（如 '20240620' → '2024'）"""
        match = re.search(r"(20\d{2})\d{4}", filename)
        if match:
            return match.group(1)
        match = re.search(r"(20\d{2})", filename)
        if match:
            return match.group(1)
        return str(datetime.now().year)

    # ------------------------------------------------------------------
    # 记录构建
    # ------------------------------------------------------------------

    def _build_record(
        self, parsed: Dict[str, Any], year: Optional[str]
    ) -> Optional[SchoolRecord]:
        """从解析后的行数据构建 SchoolRecord"""
        # 学校名称是必须的
        name = self._clean_name(parsed.get("name", ""))
        if not name or len(name) < 2:
            return None

        code_edu = self._clean_code(parsed.get("code_edu", ""))
        location = str(parsed.get("location", "")).strip()
        admin_dept = str(parsed.get("admin_department", "")).strip()
        level_raw = str(parsed.get("level", "")).strip()

        province, city = self._parse_location(location)
        level = self._normalize_level(level_raw)
        school_type = self._infer_type(name)

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        return SchoolRecord(
            code_edu=code_edu,
            name=name,
            name_aliases=[],
            level=level,
            type=school_type,
            admin_department=admin_dept if admin_dept else None,
            province=province,
            city=city,
            is_211=False,
            is_985=False,
            is_double_first_class=False,
            data_source="教育部全国高等学校名单",
            data_version=year,
            created_at=now_iso,
            updated_at=now_iso,
        )

    # ------------------------------------------------------------------
    # 字段清洗
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_name(raw: Any) -> str:
        """清洗学校名称"""
        if not raw:
            return ""
        name = str(raw).strip()
        # 去除可能的序号前缀（如 "1　北京大学"）
        name = re.sub(r"^\d+[\s　]+", "", name)
        # 去除多余的空白
        name = re.sub(r"\s+", "", name)
        return name

    @staticmethod
    def _clean_code(raw: Any) -> str:
        """
        清洗院校代码。

        教育部"学校标识码"是 10 位数字（如 4111010001），
        作为唯一标识使用。后续通过阳光高考补充 5 位高考院校代码。
        """
        if not raw:
            return ""

        code = str(raw).strip()

        # 处理科学计数法（Excel 读数字型代码）
        try:
            if "." in code or "e" in code.lower():
                # 使用 Decimal 或直接 int 转换保持精度
                code = str(int(float(code)))
        except (ValueError, OverflowError):
            pass

        # 去除非数字字符
        code = re.sub(r"[^\d]", "", code)

        # 学校标识码固定 10 位，pad 到 10 位
        if len(code) == 10:
            return code
        elif len(code) > 10:
            return code[:10]  # 异常长串截断
        elif 5 <= len(code) < 10:
            # 可能是已经截断过的 5 位码，补零到 10 位保持格式统一
            return code.zfill(10)
        else:
            return code

    @staticmethod
    def _parse_location(raw: str) -> tuple:
        """
        从"所在地"字段提取省份和城市。

        示例：
          "北京市" → ("北京市", "北京市")
          "河北省保定市" → ("河北省", "保定市")
          "新疆维吾尔自治区乌鲁木齐市" → ("新疆维吾尔自治区", "乌鲁木齐市")
        """
        if not raw:
            return (None, None)

        raw = raw.strip()

        province = None
        city = None

        # 匹配省份
        for pname in PROVINCE_NAMES:
            if raw.startswith(pname):
                province = pname
                rest = raw[len(pname):]
                # 提取城市
                if rest:
                    # 尝试匹配 "XX市" 或 "XX州" 或 "XX地区"
                    city_match = re.match(
                        r"([一-鿿]+?(?:市|州|地区|盟|区))", rest
                    )
                    if city_match:
                        city = city_match.group(1)
                    else:
                        city = rest
                else:
                    # 直辖市等
                    if province in DIRECT_MUNICIPALITIES:
                        city = province
                break

        if province is None:
            # 尝试从简称匹配
            for short, full in PROVINCE_SHORT_MAP.items():
                if raw.startswith(short):
                    province = full
                    rest = raw[len(short):]
                    if rest:
                        city_match = re.match(
                            r"([一-鿿]+?(?:市|州|地区|盟|区))", rest
                        )
                        city = city_match.group(1) if city_match else rest
                    else:
                        if full in DIRECT_MUNICIPALITIES:
                            city = full
                    break

        if province is None:
            # 最后尝试：将整个字段作为省份和城市
            province = raw
            city = raw

        return (province, city)

    @staticmethod
    def _normalize_level(raw: str) -> Optional[str]:
        """
        规范化办学层次。

        合法值: 本科 / 专科 / 职业本科
        """
        if not raw:
            return None
        raw = raw.strip()
        if "职业本科" in raw or "职业技术大学" in raw:
            return "职业本科"
        if "本科" in raw:
            return "本科"
        if "专科" in raw or "高职" in raw:
            return "专科"
        # 部分文件中办学层次写的是具体描述
        if "大学" in raw or "学院" in raw:
            # 仅凭名称无法判断本科/专科
            return None
        return None

    @staticmethod
    def _infer_type(name: str) -> Optional[str]:
        """
        从院校名称推断办学类型。

        合法值: 综合/理工/农林/医药/师范/语言/财经/政法/体育/艺术/军事/民族
        """
        if not name:
            return None
        for keywords, school_type in TYPE_KEYWORDS:
            for kw in keywords:
                if kw in name:
                    return school_type
        return "综合"


# ============================================================================
# 文件下载与搜索
# ============================================================================

class MOEFileFinder:
    """
    从教育部官网搜索最新高校名单文件。
    """

    SESSION = None

    @classmethod
    def get_session(cls) -> requests.Session:
        if cls.SESSION is None:
            cls.SESSION = requests.Session()
            cls.SESSION.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
        return cls.SESSION

    @classmethod
    def search_latest(cls) -> Optional[Dict[str, str]]:
        """
        搜索最新的高校名单文件链接。

        返回:
            {"url": 文件页面URL, "title": 标题, "file_url": 附件URL, "year": 年份}
            或 None
        """
        session = cls.get_session()

        # 策略1: 从索引页搜索
        try:
            result = cls._search_from_index(session)
            if result:
                return result
        except Exception as exc:
            logger.warning("从索引页搜索失败: %s", exc)

        # 策略2: 尝试已知 URL
        try:
            result = cls._try_known_urls(session)
            if result:
                return result
        except Exception as exc:
            logger.warning("尝试已知 URL 失败: %s", exc)

        return None

    @classmethod
    def download_file(cls, url: str, save_dir: Optional[Path] = None) -> Path:
        """
        下载文件到本地。

        参数:
            url: 文件 URL
            save_dir: 保存目录（默认 OUTPUT_DIR）

        返回:
            本地文件路径
        """
        session = cls.get_session()
        save_dir = save_dir or OUTPUT_DIR
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        logger.info("正在下载: %s", url)
        resp = session.get(url, timeout=60, stream=True)
        resp.raise_for_status()

        # 从 URL 或 Content-Disposition 获取文件名
        filename = cls._extract_filename(resp, url)
        filepath = save_dir / filename

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info("已保存: %s (%d bytes)", filepath, filepath.stat().st_size)
        return filepath

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @classmethod
    def _search_from_index(cls, session: requests.Session) -> Optional[Dict[str, str]]:
        """从教育部高校名单索引页搜索最新文件"""
        logger.info("正在访问索引页: %s", MOE_LIST_INDEX_URL)

        resp = session.get(MOE_LIST_INDEX_URL, timeout=30)
        resp.raise_for_status()
        resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")

        # 在页面中查找与"全国高等学校名单"相关的链接
        links = []
        for a_tag in soup.find_all("a", href=True):
            text = a_tag.get_text(strip=True)
            href = a_tag["href"]
            if "高等学校名单" in text or "全国高校名单" in text:
                full_url = urljoin(MOE_LIST_INDEX_URL, href)
                links.append({"url": full_url, "title": text})

        if links:
            # 取第一条（通常是最新的）
            best = links[0]
            year_match = re.search(r"(20\d{2})", best["title"])
            best["year"] = year_match.group(1) if year_match else None

            logger.info("找到候选链接: %s", best["title"])
            # 进入详情页找附件
            file_url = cls._find_attachment(session, best["url"])
            best["file_url"] = file_url
            return best

        return None

    @classmethod
    def _try_known_urls(cls, session: requests.Session) -> Optional[Dict[str, str]]:
        """尝试已知的 URL 模式"""
        for url in KNOWN_URLS:
            try:
                logger.info("尝试已知 URL: %s", url)
                resp = session.get(url, timeout=30)
                if resp.status_code == 200:
                    resp.encoding = "utf-8"
                    soup = BeautifulSoup(resp.text, "html.parser")
                    title_tag = soup.find("title")
                    title = (
                        title_tag.get_text(strip=True)
                        if title_tag else "全国高等学校名单"
                    )
                    file_url = cls._find_attachment(session, url)
                    year_match = re.search(r"(20\d{2})", url)
                    year = year_match.group(1) if year_match else None
                    return {
                        "url": url,
                        "title": title,
                        "file_url": file_url,
                        "year": year,
                    }
            except Exception:
                continue

        return None

    @classmethod
    def _find_attachment(
        cls, session: requests.Session, page_url: str
    ) -> Optional[str]:
        """在详情页中查找附件（Excel/PDF）的下载链接"""
        try:
            resp = session.get(page_url, timeout=30)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except Exception:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # 查找文件下载链接
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if re.search(r"\.(xlsx|xls|pdf)$", href, re.IGNORECASE):
                return urljoin(page_url, href)

        # 有些页面用 JavaScript 或间接链接，尝试常见模式
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "download" in href.lower() or "upload" in href.lower():
                if re.search(r"\.(xlsx|xls|pdf)$", href, re.IGNORECASE):
                    return urljoin(page_url, href)

        return None

    @staticmethod
    def _extract_filename(resp: requests.Response, url: str) -> str:
        """从响应头或 URL 中提取文件名"""
        cd = resp.headers.get("Content-Disposition", "")
        match = re.search(r'filename[^;=\n]*=["\']?([^"\'\n;]+)', cd, re.IGNORECASE)
        if match:
            return match.group(1)

        # 从 URL 提取
        parsed = url.split("/")[-1].split("?")[0]
        if parsed:
            return parsed

        # 从 Content-Type 推断扩展名
        ct = resp.headers.get("Content-Type", "")
        ext = ".bin"
        if "excel" in ct.lower() or "spreadsheet" in ct.lower():
            ext = ".xlsx"
        elif "pdf" in ct.lower():
            ext = ".pdf"

        return f"moe_school_list_{datetime.now().strftime('%Y%m%d')}{ext}"


# ============================================================================
# Scrapy Spider（仅在安装了 scrapy 时才可用）
# ============================================================================

class MOESchoolsSpider(_SpiderBase):
    """
    教育部全国高等学校名单 Scrapy Spider

    使用方式:
        cd src/crawler
        scrapy crawl moe_schools -o data/raw/schools/output.jsonl

    注意: 此类仅在安装了 scrapy 时才可用作真正的 Scrapy Spider；
         直接运行模式不需要 scrapy，会走 main() 入口。
    """

    name = "moe_schools"

    def __init__(self, *args, input_file=None, year=None, **kwargs):
        if HAS_SCRAPY:
            super().__init__(*args, **kwargs)
        self.input_file = input_file
        self.year = year
        self.parser = MOESchoolsParser()
        self.records_count = 0

    @classmethod
    def update_settings(cls, settings):
        if HAS_SCRAPY:
            super().update_settings(settings)

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        if not HAS_SCRAPY:
            return cls(*args, **kwargs)
        spider = super().from_crawler(crawler, *args, **kwargs)
        spider.allowed_domains = ["moe.gov.cn"]
        spider.start_urls = [MOE_LIST_INDEX_URL]
        spider.custom_settings = {
            "DOWNLOAD_DELAY": 3,
            "RANDOMIZE_DOWNLOAD_DELAY": True,
            "CONCURRENT_REQUESTS": 2,
        }
        return spider

    def start_requests(self):
        """Scrapy 起始请求（仅在 Scrapy 环境有效）"""
        if not HAS_SCRAPY:
            return []

        if self.input_file:
            records = self.parser.parse(self.input_file, self.year)
            for rec in records:
                self.records_count += 1
                yield rec.to_dict()
            return

        for url in [MOE_LIST_INDEX_URL] + KNOWN_URLS:
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        """解析页面（索引页或详情页）"""
        soup = BeautifulSoup(response.text, "html.parser")

        # 查找高校名单链接（索引页 → 详情页）
        for a_tag in soup.find_all("a", href=True):
            text = a_tag.get_text(strip=True)
            href = a_tag["href"]
            if "高等学校名单" in text or "全国高校名单" in text:
                full_url = urljoin(response.url, href)
                self.logger.info("找到高校名单页面: %s (%s)", text, full_url)
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_detail_page,
                    meta={"title": text},
                )
                return

        # 已是详情页（或已知 URL），直接找附件
        for result in self.parse_detail_page(response):
            yield result

    def parse_detail_page(self, response):
        """解析详情页，查找附件下载链接"""
        soup = BeautifulSoup(response.text, "html.parser")

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if re.search(r"\.(xlsx|xls|pdf)$", href, re.IGNORECASE):
                file_url = urljoin(response.url, href)
                self.logger.info("找到附件: %s", file_url)
                yield scrapy.Request(
                    file_url,
                    callback=self.parse_file,
                    meta={"year": self._extract_year(response.url)},
                )
                return

        self.logger.warning("详情页未找到附件链接: %s", response.url)

    def parse_file(self, response):
        """下载并解析文件"""
        temp_path = OUTPUT_DIR / f"_temp_{response.url.split('/')[-1]}"
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_bytes(response.body)

        year = response.meta.get("year") or self.year
        records = self.parser.parse(str(temp_path), year)

        for rec in records:
            self.records_count += 1
            yield rec.to_dict()

        try:
            temp_path.unlink()
        except OSError:
            pass

    @staticmethod
    def _extract_year(url: str) -> Optional[str]:
        match = re.search(r"(20\d{2})", url)
        return match.group(1) if match else None

    def closed(self, reason):
        """爬虫关闭时打印统计"""
        if HAS_SCRAPY:
            self.logger.info("=" * 60)
            self.logger.info("采集完成统计:")
            self.logger.info("  总条数: %d", self.records_count)
            self.logger.info("  关闭原因: %s", reason)
            self.logger.info("=" * 60)


# ============================================================================
# 统计输出
# ============================================================================

def print_statistics(records: List[SchoolRecord], errors: List[Dict]) -> None:
    """打印采集统计信息"""
    total = len(records)
    undergrad = sum(1 for r in records if r.level == "本科")
    vocational = sum(1 for r in records if r.level == "专科")
    voc_undergrad = sum(1 for r in records if r.level == "职业本科")
    unknown_level = sum(1 for r in records if not r.level)

    # 按省份统计
    province_counts: Dict[str, int] = {}
    for r in records:
        p = r.province or "未知"
        province_counts[p] = province_counts.get(p, 0) + 1

    # 按类型统计
    type_counts: Dict[str, int] = {}
    for r in records:
        t = r.type or "未知"
        type_counts[t] = type_counts.get(t, 0) + 1

    print()
    print("=" * 60)
    print("  教育部全国高等学校名单 — 采集统计")
    print("=" * 60)
    print(f"  总记录数:    {total}")
    print(f"  本科院校:    {undergrad}")
    print(f"  专科院校:    {vocational}")
    print(f"  职业本科:    {voc_undergrad}")
    print(f"  层次未知:    {unknown_level}")
    print(f"  错误数:      {len(errors)}")
    print("-" * 60)
    print(f"  数据来源:    教育部全国高等学校名单")
    versions = set(r.data_version for r in records if r.data_version)
    print(f"  数据版本:    {', '.join(sorted(versions)) if versions else '未知'}")
    print("-" * 60)
    print(f"  覆盖省份:    {len(province_counts)} 个")
    print()

    # 按省份 Top 10
    print("  省份 TOP 10:")
    for p, cnt in sorted(province_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    {p}: {cnt}")
    print()

    # 按类型分布
    print("  办学类型分布:")
    for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {t}: {cnt}")
    print()

    if errors:
        print(f"  ⚠️  解析错误: {len(errors)} 条")
        for err in errors[:5]:
            print(f"    行 {err.get('row_index', '?')}: {err.get('error', '未知错误')}")
        if len(errors) > 5:
            print(f"     ... 以及另外 {len(errors) - 5} 条错误")
        print()

    print("=" * 60)


# ============================================================================
# 直接运行入口
# ============================================================================

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="教育部全国高等学校名单爬虫 — 下载并解析高校名单",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 自动搜索最新名单
  python moe_schools_spider.py

  # 手动指定文件
  python moe_schools_spider.py --input moe_schools_2024.xlsx

  # 预览模式（只打印前5条）
  python moe_schools_spider.py --dry-run

  # 指定输出目录
  python moe_schools_spider.py --output-dir ./my_output/

  # 指定数据年份
  python moe_schools_spider.py --year 2024
        """,
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        default=None,
        help="手动指定高校名单文件路径（.xlsx/.xls/.pdf）",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=str(OUTPUT_DIR),
        help=f"输出目录（默认: {OUTPUT_DIR}）",
    )
    parser.add_argument(
        "--year", "-y",
        type=str,
        default=None,
        help="数据年份（如 '2024'），不指定则自动从文件名提取",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="预览模式：只打印前5条记录，不保存文件",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细日志输出",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1: 获取文件
    # ------------------------------------------------------------------
    parser_engine = MOESchoolsParser()
    file_path: Optional[Path] = None

    if args.input:
        file_path = Path(args.input)
        if not file_path.exists():
            print(f"错误: 文件不存在 — {file_path}", file=sys.stderr)
            sys.exit(1)
        logger.info("使用手动指定的文件: %s", file_path)

    else:
        # 自动搜索
        logger.info("正在搜索最新高校名单...")
        finder = MOEFileFinder()
        result = finder.search_latest()

        if result and result.get("file_url"):
            logger.info("找到文件: %s", result["file_url"])
            try:
                file_path = finder.download_file(result["file_url"], output_dir)
                if not args.year and result.get("year"):
                    args.year = result["year"]
            except Exception as exc:
                logger.error("下载失败: %s", exc)
                print(f"错误: 自动下载失败 — {exc}", file=sys.stderr)
                print("请手动下载文件并使用 --input 参数指定路径", file=sys.stderr)
                sys.exit(1)
        else:
            print(
                "错误: 无法自动找到最新高校名单文件。\n"
                "请手动从教育部官网下载，然后使用 --input 参数指定文件路径。\n"
                f"教育部高校名单页面: {MOE_LIST_INDEX_URL}",
                file=sys.stderr,
            )
            sys.exit(1)

    if file_path is None:
        print("错误: 未能获取到文件", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 2: 解析文件
    # ------------------------------------------------------------------
    logger.info("开始解析: %s", file_path)
    records = parser_engine.parse(str(file_path), args.year)

    if not records:
        print("警告: 未解析出任何院校记录", file=sys.stderr)
        print("请检查文件格式是否正确（支持 .xlsx/.xls/.pdf）", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 3: 输出
    # ------------------------------------------------------------------
    if args.dry_run:
        # 预览模式
        print()
        print(f"--- 预览模式: 前 {min(5, len(records))} 条记录 ---")
        print()
        for i, rec in enumerate(records[:5]):
            print(f"[{i+1}] {rec.to_jsonl_line()}")
        print()
        print_statistics(records, parser_engine.errors)
        return

    # 生成输出文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"raw_{timestamp}.jsonl"
    errors_file = output_dir / f"errors_{timestamp}.jsonl"

    # 写入 JSONL
    with open(output_file, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(rec.to_jsonl_line() + "\n")

    logger.info("已保存: %s (%d 条记录)", output_file, len(records))

    # 写入错误记录
    if parser_engine.errors:
        with open(errors_file, "w", encoding="utf-8") as f:
            for err in parser_engine.errors:
                f.write(json.dumps(err, ensure_ascii=False) + "\n")
        logger.info("错误记录: %s (%d 条)", errors_file, len(parser_engine.errors))

    # ------------------------------------------------------------------
    # Step 4: 统计
    # ------------------------------------------------------------------
    print_statistics(records, parser_engine.errors)
    print(f"输出文件: {output_file}")
    if parser_engine.errors:
        print(f"错误记录: {errors_file}")
    print()


def run_scrapy():
    """以 Scrapy 方式运行（需要安装 scrapy）"""
    if not HAS_SCRAPY:
        print("错误: 需要安装 scrapy 库，请运行: pip install scrapy", file=sys.stderr)
        sys.exit(1)

    sys.path.insert(0, str(SCRAPY_PROJECT_DIR))
    process = CrawlerProcess(_get_project_settings())
    process.crawl(MOESchoolsSpider)
    process.start()


def _get_project_settings():
    """尝试获取 Scrapy 项目设置"""
    try:
        from scrapy.utils.project import get_project_settings
        return get_project_settings()
    except Exception:
        return {}


if __name__ == "__main__":
    main()
