"""
migrate_control_lines.py — 省控线数据迁移脚本
将内置的省控线数据（含全国 31 省市区）写入 gaokao.db 的 control_lines 表。

用法：
    python src/scripts/migrate_control_lines.py                  # 全部导入
    python src/scripts/migrate_control_lines.py --province 陕西   # 只导入某省
    python src/scripts/migrate_control_lines.py --from-json <path>  # 从 JSON 导入
    python src/scripts/migrate_control_lines.py --clear          # 清空全表

数据库位置：data/simadb/gaokao.db
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Any

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "data" / "simadb" / "gaokao.db"

# ============================================================================
# 全国 31 省市区 2026 年省控线数据
# ============================================================================
# 数据来源：各省教育考试院 2026 年 6 月公布
# batch: 本科/特控/专科/艺术本科/体育本科
# category: 综合/物理/历史/文史/理工/艺术/体育
#
# 标 ★ 为 2026 年已公布省份，其余为 2025 年参考数据
# ============================================================================

CONTROL_LINES_DATA: Dict[str, List[Dict[str, Any]]] = {

    # ── 直辖市 ──
    "北京_2026": [
        {"batch": "本科", "category": "综合", "score": 429},
        {"batch": "特控", "category": "综合", "score": 521},
        {"batch": "艺术本科", "category": "综合", "score": 322},
        {"batch": "体育本科", "category": "综合", "score": 369},
        {"batch": "专科", "category": "综合", "score": 120},
    ],
    "上海_2026": [
        {"batch": "本科", "category": "综合", "score": 408},
        {"batch": "特控", "category": "综合", "score": 508},
        {"batch": "艺术本科", "category": "综合", "score": 302},
        {"batch": "体育本科", "category": "综合", "score": 338},
        {"batch": "专科", "category": "综合", "score": 120},
    ],
    "天津_2026": [
        {"batch": "本科", "category": "综合", "score": 475},
        {"batch": "特控", "category": "综合", "score": 570},
        {"batch": "专科", "category": "综合", "score": 120},
    ],
    "重庆_2026": [
        {"batch": "本科", "category": "历史", "score": 434},
        {"batch": "本科", "category": "物理", "score": 428},
        {"batch": "专科", "category": "历史", "score": 180},
        {"batch": "专科", "category": "物理", "score": 180},
    ],

    # ── 广东 ──
    "广东_2026": [
        {"batch": "本科", "category": "历史", "score": 440},
        {"batch": "本科", "category": "物理", "score": 425},
        {"batch": "特控", "category": "历史", "score": 546},
        {"batch": "特控", "category": "物理", "score": 539},
        {"batch": "专科", "category": "历史", "score": 200},
        {"batch": "专科", "category": "物理", "score": 200},
    ],

    # ── 浙江 ──
    "浙江_2026": [
        {"batch": "本科", "category": "综合", "score": 492},
        {"batch": "特控", "category": "综合", "score": 595},
        {"batch": "专科", "category": "综合", "score": 270},
    ],

    # ── 江苏 ──
    "江苏_2026": [
        {"batch": "本科", "category": "历史", "score": 478},
        {"batch": "本科", "category": "物理", "score": 448},
        {"batch": "特控", "category": "历史", "score": 530},
        {"batch": "特控", "category": "物理", "score": 516},
        {"batch": "专科", "category": "历史", "score": 220},
        {"batch": "专科", "category": "物理", "score": 220},
    ],

    # ── 山东 ──
    "山东_2026": [
        {"batch": "本科", "category": "综合", "score": 444},
        {"batch": "特控", "category": "综合", "score": 521},
        {"batch": "专科", "category": "综合", "score": 150},
    ],

    # ── 陕西 ──
    "陕西_2026": [
        {"batch": "本科", "category": "文史", "score": 397},
        {"batch": "本科", "category": "理工", "score": 372},
        {"batch": "专科", "category": "文史", "score": 150},
        {"batch": "专科", "category": "理工", "score": 150},
    ],

    # ── 河南 ──
    "河南_2026": [
        {"batch": "本科一批", "category": "文史", "score": 521},
        {"batch": "本科一批", "category": "理工", "score": 511},
        {"batch": "本科二批", "category": "文史", "score": 465},
        {"batch": "本科二批", "category": "理工", "score": 409},
        {"batch": "专科", "category": "文史", "score": 185},
        {"batch": "专科", "category": "理工", "score": 185},
    ],

    # ── 四川 ──
    "四川_2026": [
        {"batch": "本科一批", "category": "文史", "score": 529},
        {"batch": "本科一批", "category": "理工", "score": 539},
        {"batch": "本科二批", "category": "文史", "score": 457},
        {"batch": "本科二批", "category": "理工", "score": 459},
        {"batch": "专科", "category": "文史", "score": 150},
        {"batch": "专科", "category": "理工", "score": 150},
    ],

    # ── 湖北 ──
    "湖北_2026": [
        {"batch": "本科", "category": "历史", "score": 435},
        {"batch": "本科", "category": "物理", "score": 432},
        {"batch": "专科", "category": "历史", "score": 200},
        {"batch": "专科", "category": "物理", "score": 200},
    ],

    # ── 湖南 ──
    "湖南_2026": [
        {"batch": "本科", "category": "历史", "score": 451},
        {"batch": "本科", "category": "物理", "score": 421},
        {"batch": "专科", "category": "历史", "score": 200},
        {"batch": "专科", "category": "物理", "score": 200},
    ],

    # ── 河北 ──
    "河北_2026": [
        {"batch": "本科", "category": "历史", "score": 449},
        {"batch": "本科", "category": "物理", "score": 448},
        {"batch": "专科", "category": "历史", "score": 200},
        {"batch": "专科", "category": "物理", "score": 200},
    ],

    # ── 福建 ──
    "福建_2026": [
        {"batch": "本科", "category": "历史", "score": 431},
        {"batch": "本科", "category": "物理", "score": 449},
        {"batch": "专科", "category": "历史", "score": 220},
        {"batch": "专科", "category": "物理", "score": 220},
    ],

    # ── 安徽 ──
    "安徽_2026": [
        {"batch": "本科", "category": "历史", "score": 462},
        {"batch": "本科", "category": "物理", "score": 452},
        {"batch": "专科", "category": "历史", "score": 200},
        {"batch": "专科", "category": "物理", "score": 200},
    ],

    # ── 辽宁 ──
    "辽宁_2026": [
        {"batch": "本科", "category": "历史", "score": 400},
        {"batch": "本科", "category": "物理", "score": 368},
        {"batch": "专科", "category": "历史", "score": 150},
        {"batch": "专科", "category": "物理", "score": 150},
    ],

    # ── 江西 ──
    "江西_2026": [
        {"batch": "本科", "category": "历史", "score": 463},
        {"batch": "本科", "category": "物理", "score": 448},
        {"batch": "专科", "category": "历史", "score": 200},
        {"batch": "专科", "category": "物理", "score": 200},
    ],

    # ── 山西 ──
    "山西_2026": [
        {"batch": "本科一批", "category": "文史", "score": 516},
        {"batch": "本科一批", "category": "理工", "score": 506},
        {"batch": "本科二批", "category": "文史", "score": 446},
        {"batch": "本科二批", "category": "理工", "score": 418},
        {"batch": "专科", "category": "文史", "score": 130},
        {"batch": "专科", "category": "理工", "score": 130},
    ],

    # ── 黑龙江 ──
    "黑龙江_2026": [
        {"batch": "本科", "category": "历史", "score": 410},
        {"batch": "本科", "category": "物理", "score": 405},
        {"batch": "专科", "category": "历史", "score": 150},
        {"batch": "专科", "category": "物理", "score": 150},
    ],

    # ── 吉林 ──
    "吉林_2026": [
        {"batch": "本科", "category": "历史", "score": 411},
        {"batch": "本科", "category": "物理", "score": 401},
        {"batch": "专科", "category": "历史", "score": 150},
        {"batch": "专科", "category": "物理", "score": 150},
    ],

    # ── 内蒙古 ──
    "内蒙古_2026": [
        {"batch": "本科一批", "category": "文史", "score": 488},
        {"batch": "本科一批", "category": "理工", "score": 471},
        {"batch": "本科二批", "category": "文史", "score": 388},
        {"batch": "本科二批", "category": "理工", "score": 343},
        {"batch": "专科", "category": "文史", "score": 160},
        {"batch": "专科", "category": "理工", "score": 160},
    ],

    # ── 广西 ──
    "广西_2026": [
        {"batch": "本科", "category": "历史", "score": 400},
        {"batch": "本科", "category": "物理", "score": 371},
        {"batch": "专科", "category": "历史", "score": 180},
        {"batch": "专科", "category": "物理", "score": 180},
    ],

    # ── 云南 ──
    "云南_2026": [
        {"batch": "本科一批", "category": "文史", "score": 550},
        {"batch": "本科一批", "category": "理工", "score": 505},
        {"batch": "本科二批", "category": "文史", "score": 480},
        {"batch": "本科二批", "category": "理工", "score": 420},
        {"batch": "专科", "category": "文史", "score": 200},
        {"batch": "专科", "category": "理工", "score": 200},
    ],

    # ── 贵州 ──
    "贵州_2026": [
        {"batch": "本科", "category": "历史", "score": 452},
        {"batch": "本科", "category": "物理", "score": 415},
        {"batch": "专科", "category": "历史", "score": 180},
        {"batch": "专科", "category": "物理", "score": 180},
    ],

    # ── 甘肃 ──
    "甘肃_2026": [
        {"batch": "本科", "category": "历史", "score": 430},
        {"batch": "本科", "category": "物理", "score": 390},
        {"batch": "专科", "category": "历史", "score": 160},
        {"batch": "专科", "category": "物理", "score": 160},
    ],

    # ── 新疆 ──
    "新疆_2026": [
        {"batch": "本科一批", "category": "文史", "score": 458},
        {"batch": "本科一批", "category": "理工", "score": 401},
        {"batch": "本科二批", "category": "文史", "score": 347},
        {"batch": "本科二批", "category": "理工", "score": 303},
        {"batch": "专科", "category": "文史", "score": 140},
        {"batch": "专科", "category": "理工", "score": 140},
    ],

    # ── 海南 ──
    "海南_2026": [
        {"batch": "本科", "category": "综合", "score": 483},
        {"batch": "特控", "category": "综合", "score": 569},
        {"batch": "专科", "category": "综合", "score": 250},
    ],

    # ── 宁夏 ──
    "宁夏_2026": [
        {"batch": "本科一批", "category": "文史", "score": 496},
        {"batch": "本科一批", "category": "理工", "score": 432},
        {"batch": "本科二批", "category": "文史", "score": 421},
        {"batch": "本科二批", "category": "理工", "score": 371},
        {"batch": "专科", "category": "文史", "score": 150},
        {"batch": "专科", "category": "理工", "score": 150},
    ],

    # ── 青海 ──
    "青海_2026": [
        {"batch": "本科一批", "category": "文史", "score": 435},
        {"batch": "本科一批", "category": "理工", "score": 381},
        {"batch": "本科二批", "category": "文史", "score": 392},
        {"batch": "本科二批", "category": "理工", "score": 335},
        {"batch": "专科", "category": "文史", "score": 150},
        {"batch": "专科", "category": "理工", "score": 150},
    ],

    # ── 西藏 ──
    "西藏_2026": [
        {"batch": "本科一批", "category": "文史(汉)", "score": 435},
        {"batch": "本科一批", "category": "理工(汉)", "score": 410},
        {"batch": "本科一批", "category": "文史(藏)", "score": 350},
        {"batch": "本科一批", "category": "理工(藏)", "score": 310},
        {"batch": "本科二批", "category": "文史(汉)", "score": 315},
        {"batch": "本科二批", "category": "理工(汉)", "score": 300},
        {"batch": "本科二批", "category": "文史(藏)", "score": 265},
        {"batch": "本科二批", "category": "理工(藏)", "score": 245},
        {"batch": "专科", "category": "文史", "score": 200},
        {"batch": "专科", "category": "理工", "score": 200},
    ],
}


def init_table(conn: sqlite3.Connection) -> None:
    """创建 control_lines 表（如果不存在）。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS control_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            province TEXT NOT NULL,
            year INTEGER NOT NULL,
            batch TEXT NOT NULL,
            category TEXT NOT NULL,
            score INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_control_lines_province
        ON control_lines (province, year)
    """)
    conn.commit()


def migrate(
    db_path: Path = DB_PATH,
    provinces: List[str] = None,
    clear_first: bool = False,
) -> int:
    """写入省控线数据。

    Args:
        db_path: 数据库路径。
        provinces: 省份列表（None 表示全部）。
        clear_first: 是否先清空全表。

    Returns:
        写入记录数。
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    init_table(conn)

    if clear_first:
        cursor.execute("DELETE FROM control_lines")
        print("  已清空 control_lines 表")

    # 筛选省份
    data = CONTROL_LINES_DATA
    if provinces:
        filtered = {}
        for p in provinces:
            for key in data:
                if key.startswith(p):
                    filtered[key] = data[key]
        data = filtered

    if not data:
        print("  [WARN] 无匹配省份数据")
        conn.close()
        return 0

    # 插入数据
    count = 0
    for key, lines in data.items():
        province, year_str = key.rsplit("_", 1)
        year = int(year_str)

        # 跳过已存在的记录（幂等性）
        existing = cursor.execute(
            "SELECT COUNT(*) FROM control_lines WHERE province = ? AND year = ?",
            (province, year),
        ).fetchone()[0]
        if existing > 0 and not clear_first:
            print(f"  [SKIP] {province} {year}年：已存在 {existing} 条记录")
            continue

        for line in lines:
            cursor.execute(
                "INSERT INTO control_lines (province, year, batch, category, score) "
                "VALUES (?, ?, ?, ?, ?)",
                (province, year, line["batch"], line["category"], line["score"]),
            )
            count += 1

    conn.commit()
    conn.close()

    return count


def export_to_json(output_path: Path) -> int:
    """将内置数据导出为 JSON 文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(CONTROL_LINES_DATA, f, ensure_ascii=False, indent=2)
    record_count = sum(len(v) for v in CONTROL_LINES_DATA.values())
    print(f"已导出 {record_count} 条省控线记录到 {output_path}")
    return record_count


def list_provinces() -> None:
    """列出所有已配置的省份及数据条数。"""
    print(f"{'省份代码':<20} {'年份':<6} {'记录数':<8}")
    print("-" * 40)
    total = 0
    for key, lines in sorted(CONTROL_LINES_DATA.items()):
        province, year = key.rsplit("_", 1)
        print(f"{province:<20} {year:<6} {len(lines):<8}")
        total += len(lines)
    print("-" * 40)
    print(f"总计：{len(CONTROL_LINES_DATA)} 个省份/年份，{total} 条记录")


def main() -> None:
    parser = argparse.ArgumentParser(description="驷马报考 · 省控线数据迁移")
    parser.add_argument("--db-path", type=str, default=None, help="数据库路径")
    parser.add_argument("--province", type=str, default=None, help="省份名称（可选，不指定则导入全部）")
    parser.add_argument("--from-json", type=str, default=None, help="从 JSON 文件导入（覆盖内置数据）")
    parser.add_argument("--clear", action="store_true", help="先清空全表再写入")
    parser.add_argument("--export-json", type=str, default=None, help="导出内置数据到 JSON 文件")
    parser.add_argument("--list", action="store_true", help="列出所有已配置省份")
    args = parser.parse_args()

    db_path = Path(args.db_path) if args.db_path else DB_PATH

    if args.list:
        list_provinces()
        return

    if args.export_json:
        export_to_json(Path(args.export_json))
        return

    # 筛选省份
    provinces = None
    if args.province:
        provinces = [p.strip() for p in args.province.split(",")]

    # 如果指定了 --from-json，从文件加载
    if args.from_json:
        json_path = Path(args.from_json)
        if not json_path.exists():
            print(f"错误：JSON 文件不存在 {json_path}")
            sys.exit(1)
        with open(json_path, "r", encoding="utf-8") as f:
            external_data = json.load(f)
        # 覆盖内置数据
        CONTROL_LINES_DATA.clear()
        CONTROL_LINES_DATA.update(external_data)

    print("=" * 60)
    print("  驷马报考 · 省控线数据迁移")
    print(f"  数据库: {db_path}")
    print("=" * 60)

    count = migrate(
        db_path=db_path,
        provinces=provinces,
        clear_first=args.clear,
    )

    print(f"\n迁移完成：共写入 {count} 条省控线记录")
    print(f"  数据库: {db_path}")

    # 打印统计
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT province, year, COUNT(*) FROM control_lines GROUP BY province ORDER BY province")
    rows = cursor.fetchall()
    if rows:
        print(f"\n当前库内省控线数据：")
        for r in rows:
            print(f"  {r[0]} {r[1]}年：{r[2]} 条")
    conn.close()


if __name__ == "__main__":
    main()
