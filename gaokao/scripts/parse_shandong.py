#!/usr/bin/env python3
"""Parse Shandong XLS files into JSONL"""
import json
import os
import re
import xlrd

BASE_DIR = r'D:\WorkBuddy\gaokao-database'

def parse_shandong_xls(year):
    xls_path = os.path.join(BASE_DIR, 'scripts', f'shandong_{year}.xls')
    workbook = xlrd.open_workbook(xls_path)
    sheet = workbook.sheet_by_index(0)
    
    print(f"[山东{year}] Sheet: {sheet.name}, rows: {sheet.nrows}, cols: {sheet.ncols}")
    
    # Print first 5 rows to understand structure
    for i in range(min(5, sheet.nrows)):
        row = [str(sheet.cell_value(i, c))[:50] for c in range(sheet.ncols)]
        print(f"  Row {i}: {row}")
    
    records = []
    for r in range(2, sheet.nrows):  # Skip title row 0 and header row 1
        try:
            major_cell = str(sheet.cell_value(r, 1))  # 专业代号及名称 (col 1)
            school_cell = str(sheet.cell_value(r, 2))  # 院校代号及名称 (col 2)
            plan_cell = str(sheet.cell_value(r, 3))  # 投档计划数 (col 3)
            rank_cell = str(sheet.cell_value(r, 4))  # 投档最低位次 (col 4)
            
            if not major_cell or not school_cell:
                continue
            
            # Parse school_cell: format like "A001北京大学" or "B123清华大学"
            # The format is: code + school_name
            school_match = re.match(r'[A-Z]\d+\s*(.+)', school_cell)
            if school_match:
                school_name = school_match.group(1).strip()
            else:
                school_name = school_cell.strip()
            
            # Parse major_cell: format like "16文科试验班类(文科基础类专业)"
            # The format is: number + major_name or just major_name
            major_match = re.match(r'\d+\s*(.+)', major_cell)
            if major_match:
                major_name = major_match.group(1).strip()
            else:
                major_name = major_cell.strip()
            
            # Parse rank
            try:
                rank = int(float(rank_cell)) if rank_cell and rank_cell != '' else None
            except (ValueError, TypeError):
                rank = None
            
            records.append({
                'school_name': school_name,
                'major_name': major_name,
                'admit_score_min': None,  # Shandong only publishes rank, not score
                'admit_rank_min': rank,
                'year': year,
                'province': '山东'
            })
        except Exception as e:
            print(f"  Error on row {r}: {e}")
            continue
    
    print(f"[山东{year}] Extracted {len(records)} records")
    return records

def save_records(records, year):
    province = '山东'
    output_dir = os.path.join(BASE_DIR, 'data', 'raw', 'admission', province, str(year))
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, f'admission_{year}.jsonl')
    with open(output_file, 'w', encoding='utf-8') as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    
    print(f"Saved {len(records)} records to {output_file}")

if __name__ == '__main__':
    for year in [2022, 2023]:
        records = parse_shandong_xls(year)
        if records:
            save_records(records, year)
