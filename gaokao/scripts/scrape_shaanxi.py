#!/usr/bin/env python3
"""Scrape Shaanxi 2022 & 2023 admission data from sneac.com"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re

BASE_DIR = r'D:\WorkBuddy\gaokao-database'

# Shaanxi publishes 本科一批正式投档情况统计表
# 2023: https://www.sneea.cn/info/1027/13073.htm (征集) - but also has 正式投档
# Let me find the 正式投档 pages

URLS = {
    2023: {
        '正式投档文史': 'http://www.sneac.com/htm/2023/2023YBZS-WS.html',
        '正式投档理工': 'http://www.sneac.com/htm/2023/2023YBZS-LG.html',
    },
    2022: {
        '正式投档文史': 'https://www.sneac.com/2022/2022YBZS-WS.html',
        '正式投档理工': 'https://www.sneac.com/2022/2022YBZS-LG.html',
    }
}

# Also try 本科二批
URLS_2 = {
    2023: {
        '二批文史': 'http://www.sneac.com/htm/2023/2023EBZS-WS.html',
        '二批理工': 'http://www.sneac.com/htm/2023/2023EBZS-LG.html',
    },
    2022: {
        '二批文史': 'https://www.sneac.com/2022/2022ebzjt1.htm',
        '二批理工': 'https://www.sneac.com/2022/2022ebzjt2.htm',
    }
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def parse_html_table_from_url(url, year, category):
    """Parse HTML table from sneac.com"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.encoding = 'utf-8'
    except Exception as e:
        print(f"[陕西{year}] Failed to fetch {url}: {e}")
        return []
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    table = soup.find('table')
    if not table:
        print(f"[陕西{year}] No table found at {url}")
        return []
    
    rows = table.find_all('tr')
    print(f"[陕西{year} {category}] Found {len(rows)} rows")
    
    records = []
    for row in rows:
        cols = row.find_all(['td', 'th'])
        if len(cols) < 6:
            continue
        
        cells = [c.get_text(strip=True) for c in cols]
        
        # Skip header
        first = cells[0] if cells else ''
        if any(kw in first for kw in ['序号', '科类', '院校']):
            continue
        
        try:
            # Shaanxi format: 序号 | 科类 | 院校代号 | 院校名称 | 实际投档人数 | 最低分 | 最低位次
            school_name = cells[3] if len(cells) > 3 else ''
            score_str = cells[5] if len(cells) > 5 else '0'
            rank_str = cells[6] if len(cells) > 6 else '0'
            
            # Parse score
            score = None
            try:
                score = int(float(score_str))
            except (ValueError, TypeError):
                pass
            
            # Parse rank
            rank = None
            try:
                rank = int(float(rank_str))
            except (ValueError, TypeError):
                pass
            
            # Fix: In Shaanxi data, the columns are: 最低分(score) then 最低位次(rank)
            # BUT for some entries from formal投档 (正式投档), the format might differ
            # Let me check: if score is very small (like 21) and rank is large (like 662), swap
            if score is not None and score < 2000 and rank is not None and rank > 100:
                # These are actually rank and score swapped
                score, rank = rank, score
            
            if school_name and len(school_name) > 1:
                records.append({
                    'school_name': school_name,
                    'major_name': category,  # 文史/理工
                    'admit_score_min': score,
                    'admit_rank_min': rank,
                    'year': year,
                    'province': '陕西'
                })
        except (IndexError, ValueError):
            continue
    
    return records

def save_records(records, year):
    province = '陕西'
    output_dir = os.path.join(BASE_DIR, 'data', 'raw', 'admission', province, str(year))
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, f'admission_{year}.jsonl')
    with open(output_file, 'w', encoding='utf-8') as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    
    print(f"Saved {len(records)} records to {output_file}")

if __name__ == '__main__':
    for year in [2022, 2023]:
        all_records = []
        
        # Try 本科一批
        if year in URLS:
            for cat, url in URLS[year].items():
                recs = parse_html_table_from_url(url, year, cat)
                all_records.extend(recs)
        
        # Try 本科二批
        if year in URLS_2:
            for cat, url in URLS_2[year].items():
                recs = parse_html_table_from_url(url, year, cat)
                all_records.extend(recs)
        
        print(f"[陕西{year}] Total records: {len(all_records)}")
        if all_records:
            save_records(all_records, year)
