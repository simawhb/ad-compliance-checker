"""
B站评论 school_id 关联修复脚本
根据 forum.title 中的学校名匹配 schools.name，将 code_edu 填入 forum.school_id
"""
import sqlite3
import re
from typing import List, Tuple


def create_school_mapping(db_path: str) -> dict:
    """创建学校名到 code_edu 的映射表"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 查询所有学校，创建模糊匹配词典
    cur.execute("SELECT name, code_edu FROM schools WHERE name IS NOT NULL AND code_edu IS NOT NULL")
    schools = cur.fetchall()

    # 创建映射：学校名 -> code_edu
    mapping = {}
    for name, code in schools:
        if name and code:
            mapping[name.strip()] = code.strip()

    # 特殊处理：提取简称（如“清华”对应“清华大学”）
    abbreviations = {}
    for name, code in schools:
        if name and code:
            # 提取常见简称：北京大学 -> 北大，清华大学 -> 清华
            if name.endswith('大学') or name.endswith('学院'):
                short_name = name.replace('大学', '').replace('学院', '')
                if len(short_name) >= 2:
                    abbreviations[short_name] = code

    mapping.update(abbreviations)

    cur.close()
    conn.close()
    return mapping


def find_school_in_title(title: str, mapping: dict) -> str:
    """在标题中查找学校名，返回对应的 code_edu"""
    # 按长度排序，优先匹配更长的学校名
    sorted_names = sorted(mapping.keys(), key=len, reverse=True)

    for school_name in sorted_names:
        # 使用正则匹配，允许一些变体（如“大学”和“大学”之间的空格）
        pattern = re.escape(school_name).replace(r'\ ', r'\s*')
        if re.search(pattern, title):
            return mapping[school_name]

    return None


def update_forum_school_ids(db_path: str):
    """更新 forum 表中的 school_id"""
    mapping = create_school_mapping(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 查询所有没有 school_id 的论坛帖子
    cur.execute("""
        SELECT rowid, title
        FROM forum
        WHERE school_id IS NULL OR school_id = ''
    """)
    rows = cur.fetchall()

    updated_count = 0
    for rowid, title in rows:
        if not title:
            continue

        school_code = find_school_in_title(title, mapping)
        if school_code:
            cur.execute(
                "UPDATE forum SET school_id = ? WHERE rowid = ?",
                (school_code, rowid)
            )
            updated_count += 1
            print(f"更新: {rowid} -> {school_code}")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n总共更新了 {updated_count} 条记录")
    return updated_count


if __name__ == "__main__":
    db_path = "data/simadb/gaokao.db"
    print("开始修复 B站评论的 school_id 关联...")
    count = update_forum_school_ids(db_path)
    print(f"修复完成，共更新 {count} 条记录")
