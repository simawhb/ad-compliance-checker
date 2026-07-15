"""
数据导入脚本：将 raw JSONL 和 MOE 院校 XLS 导入 SQLite 数据库

用法：
    python src/scripts/import_to_sqlite.py [--db-path <path>]

数据库位置：data/simadb/gaokao.db（默认）
"""

import json
import os
import re
import sqlite3
import sys
import argparse
from pathlib import Path

import xlrd

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "data" / "simadb" / "gaokao.db"

def _resolve_data(subpath: str) -> Path:
    """解析数据目录路径，优先 data/raw/，回退 src/data/raw/"""
    p1 = ROOT / "data" / "raw" / subpath
    if p1.exists():
        return p1
    p2 = ROOT / "src" / "data" / "raw" / subpath
    return p2 if p2.exists() else p1


def parse_schools_xls(xls_path: Path) -> list[dict]:
    """解析教育部全国高校名单 .xls 文件，返回院校记录列表"""
    wb = xlrd.open_workbook(str(xls_path))
    sheet = wb.sheet_by_index(0)
    schools = []

    for r in range(sheet.nrows):
        row = [sheet.cell_value(r, c) for c in range(sheet.ncols)]
        # row[0] 是序号，可能是 float(1.0) 或字符串如"北京市（92所）"
        seq = row[0]
        if isinstance(seq, float) and seq == int(seq):
            seq = int(seq)
        else:
            # 跳过标题行和省份分组行
            continue

        # 清洗备注（备注列可能是"本科"或空，说明办学层次在第5列）
        school_id_code = row[2]
        if isinstance(school_id_code, float):
            school_id_code = str(int(school_id_code))

        schools.append({
            "seq": seq,
            "name": str(row[1]).strip(),
            "code_edu": school_id_code,
            "admin_department": str(row[3]).strip(),
            "location": str(row[4]).strip(),
            "level": str(row[5]).strip(),
            "remarks": str(row[6]).strip() if row[6] else "",
        })

    return schools


def infer_sql_type(value) -> str:
    """根据 Python 值推断 SQLite 类型"""
    if value is None:
        return "TEXT"
    if isinstance(value, bool):
        return "INTEGER"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    return "TEXT"


def merge_field_types(records: list[dict]) -> dict[str, str]:
    """合并多条记录，确定每个字段的最终类型（向上兼容：INTEGER ⊂ REAL ⊂ TEXT）"""
    type_priority = {"INTEGER": 0, "REAL": 1, "TEXT": 2}
    merged = {}
    for rec in records:
        for k, v in rec.items():
            t = infer_sql_type(v)
            if k not in merged:
                merged[k] = t
            else:
                if type_priority[t] > type_priority[merged[k]]:
                    merged[k] = t
    return merged


def sanitize_column_name(name: str) -> str:
    """把非法字符替换为下划线"""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def get_primary_key_columns(table_name: str, records: list[dict]) -> list[str]:
    """根据表名和字段，推断主键列名（用于 INSERT OR REPLACE 的冲突检测）"""
    fields = list(records[0].keys()) if records else []
    pk_map = {
        "schools": ["code_edu"],
        "admission": ["school_name", "major_name", "batch", "year", "province"],
        "forum": ["thread_id", "platform"],
        "jobs": ["city", "keyword"],
    }
    if table_name in pk_map:
        return pk_map[table_name]
    return [fields[0]] if fields else []


def create_table_with_pk(conn: sqlite3.Connection, table_name: str, records: list[dict], col_map: dict[str, str]):
    """创建表，带主键定义"""
    if not records:
        return

    field_types = merge_field_types(records)
    pk_cols = get_primary_key_columns(table_name, records)
    pk_safe = [sanitize_column_name(c) for c in pk_cols]

    columns = []
    for field, ftype in field_types.items():
        safe = col_map.get(field, sanitize_column_name(field))
        columns.append(f'"{safe}" {ftype}')

    if pk_safe:
        pk_clause = ", ".join(f'"{c}"' for c in pk_safe)
        columns.append(f"PRIMARY KEY ({pk_clause})")

    cols_sql = ", ".join(columns)
    sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({cols_sql});'
    conn.execute(sql)


def import_jsonl(conn: sqlite3.Connection, jsonl_path: Path, table_name: str):
    """将单个 JSONL 文件导入 SQLite 表"""
    if not jsonl_path.exists():
        print(f"  [SKIP] 文件不存在: {jsonl_path}")
        return 0

    records = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"  [WARN] JSON 解析失败: {e}")

    if not records:
        print(f"  [WARN] 空文件: {jsonl_path}")
        return 0

    field_types = merge_field_types(records)
    col_map = {f: sanitize_column_name(f) for f in field_types}

    create_table_with_pk(conn, table_name, records, col_map)

    # 检查并迁移表结构：如果已有表缺少新数据的列，自动 ALTER TABLE 补充
    cursor = conn.execute(f'PRAGMA table_info("{table_name}")')
    existing_cols = {row[1] for row in cursor.fetchall()}
    missing_cols = {safe for safe in col_map.values() if safe not in existing_cols and safe not in ("PRIMARY KEY",)}
    for col in missing_cols:
        ftype = field_types.get(col, "TEXT")
        try:
            conn.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{col}" {ftype}')
            print(f"    → 已补充列: {col} ({ftype})")
        except Exception as e:
            print(f"    → 补充列失败 {col}: {e}")

    fields = list(field_types.keys())
    safe_fields = [col_map[f] for f in fields]
    placeholders = ", ".join(["?"] * len(fields))
    cols_str = ", ".join(f'"{c}"' for c in safe_fields)

    sql = f'INSERT OR REPLACE INTO "{table_name}" ({cols_str}) VALUES ({placeholders})'

    cursor = conn.cursor()
    count = 0
    for rec in records:
        values = [rec.get(f) for f in fields]
        cursor.execute(sql, values)
        count += 1

    conn.commit()
    return count


def import_schools(conn: sqlite3.Connection, records: list[dict]):
    """将院校记录导入 schools 表"""
    table_name = "schools"
    field_types = merge_field_types(records)
    col_map = {f: sanitize_column_name(f) for f in field_types}

    create_table_with_pk(conn, table_name, records, col_map)

    fields = list(field_types.keys())
    safe_fields = [col_map[f] for f in fields]
    placeholders = ", ".join(["?"] * len(fields))
    cols_str = ", ".join(f'"{c}"' for c in safe_fields)

    sql = f'INSERT OR REPLACE INTO "{table_name}" ({cols_str}) VALUES ({placeholders})'
    cursor = conn.cursor()
    for rec in records:
        values = [rec.get(f) for f in fields]
        cursor.execute(sql, values)

    conn.commit()
    return len(records)


def main():
    parser = argparse.ArgumentParser(description="驷马报考 · 数据导入脚本")
    parser.add_argument("--db-path", type=str, default=None, help="数据库路径（默认 data/simadb/gaokao.db）")
    args = parser.parse_args()

    db_path = Path(args.db_path) if args.db_path else DB_PATH

    print("=" * 60)
    print("  驷马报考 · 数据导入脚本")
    print(f"  数据库: {db_path}")
    print("=" * 60)

    # 确保目录存在
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    total = 0

    # 1. 导入院校数据
    print("\n[1/4] 导入院校数据 (MOE XLS)...")
    xls_path = ROOT / "data" / "raw" / "schools" / "W020260618416094865984.xls"
    if xls_path.exists():
        schools = parse_schools_xls(xls_path)
        n = import_schools(conn, schools)
        print(f"  ✓ 导入 {n} 条院校记录")
        total += n
    else:
        print(f"  [SKIP] 找不到 {xls_path}")

    # 2. 导入录取数据
    print("\n[2/4] 导入录取数据...")
    admission_base = _resolve_data("admission")
    if admission_base.exists():
        # 遍历所有省份和年份目录
        for jsonl_file in sorted(admission_base.rglob("*.jsonl")):
            n = import_jsonl(conn, jsonl_file, "admission")
            print(f"  ✓ {jsonl_file.relative_to(ROOT)}: {n} 条")
            total += n
    else:
        print(f"  [SKIP] 无录取数据目录")

    # 3. 导入论坛口碑数据
    print("\n[3/4] 导入论坛数据...")
    forum_dir = _resolve_data("forum/bilibili")
    if forum_dir.exists():
        forum_files = sorted(forum_dir.glob("*.jsonl"))
        for ff in forum_files:
            n = import_jsonl(conn, ff, "forum")
            print(f"  ✓ {ff.name}: {n} 条")
            total += n
    else:
        print(f"  [SKIP] 无论坛数据目录")

    # 4. 导入招聘数据
    print("\n[4/4] 导入招聘数据...")
    jobs_dir = _resolve_data("employment/jobs")
    if jobs_dir.exists():
        jobs_files = sorted(jobs_dir.glob("*.jsonl"))
        for jf in jobs_files:
            n = import_jsonl(conn, jf, "jobs")
            print(f"  ✓ {jf.name}: {n} 条")
            total += n
    else:
        print(f"  [SKIP] 无招聘数据目录")

    # 汇总
    print(f"\n{'=' * 60}")
    print(f"  导入完成！总计 {total} 条记录")
    print(f"  数据库: {db_path}")
    print(f"{'=' * 60}")

    # 打印表统计
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cursor.fetchall()]
    for t in tables:
        cursor.execute(f'SELECT COUNT(*) FROM "{t}"')
        cnt = cursor.fetchone()[0]
        print(f"  [{t}] {cnt} 行")

    conn.close()


if __name__ == "__main__":
    main()
