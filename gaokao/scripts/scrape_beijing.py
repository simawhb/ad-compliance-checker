#!/usr/bin/env python3
"""Scrape Beijing 2022 & 2023 admission data from bjeea.cn"""

import requests
from bs4 import BeautifulSoup
import json
import os

BASE_DIR = r'D:\WorkBuddy\gaokao-database'

URLS = {
    2023: 'https://www.bjeea.cn/html/gkgz/tzgg/2023/0717/84120.html',
    2022: 'https://www.bjeea.cn/html/gkgz/tzgg/2022/0717/82188.html',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def parse_score(value):
    value = value.strip()
    if not value or value == '\u2014' or value == '-' or value == '':
        return None
    try:
        return int(float(value))
    except ValueError:
        return None

def parse_beijing_page(year):
    url = URLS[year]
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.encoding = 'utf-8'
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    table = soup.find('table')
    if not table:
        tables = soup.find_all('table')
        print(f"[北京{year}] Found {len(tables)} tables")
        if tables:
            table = tables[0]
        else:
            print(f"[北京{year}] No table found, page snippet: {resp.text[:500]}")
            return []
    
    rows = table.find_all('tr')
    print(f"[北京{year}] Found {len(rows)} rows in table")
    
    records = []
    for row in rows:
        cols = row.find_all(['td', 'th'])
        if len(cols) < 6:
            continue
        
        cells = [c.get_text(strip=True) for c in cols]
        
        # Skip header rows
        first = cells[0] if cells else ''
        if any(kw in first for kw in ['院校', '序号', '专业']):
            continue
        
        try:
            school_name = cells[2] if len(cells) > 2 else (cells[1] if len(cells) > 1 else '')
            major_name = cells[3] if len(cells) > 3 else ''
            # Score is typically at index 5 (总分)
            score = None
            if len(cells) > 5:
                score = parse_score(cells[5])
            
            if school_name and score and len(school_name) > 1:
                records.append({
                    'school_name': school_name,
                    'major_name': major_name,
                    'admit_score_min': score,
                    'admit_rank_min': None,
                    'year': year,
                    'province': '北京'
                })
        except (IndexError, ValueError):
            continue
    
    print(f"[北京{year}] Extracted {len(records)} records")
    return records

def save_records(records, year):
    province = '北京'
    output_dir = os.path.join(BASE_DIR, 'data', 'raw', 'admission', province, str(year))
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, f'admission_{year}.jsonl')
    with open(output_file, 'w', encoding='utf-8') as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    
    print(f"Saved {len(records)} records to {output_file}")

if __name__ == '__main__':
    for year in [2022, 2023]:
        records = parse_beijing_page(year)
        if records:
            save_records(records, year)
        else:
            print(f"[北京{year}] No records extracted")
