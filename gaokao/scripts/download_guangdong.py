#!/usr/bin/env python3
"""Download Guangdong 2022 & 2023 PDF投档数据 and extract to JSONL"""

import requests
import json
import os
import re

BASE_DIR = r'D:\WorkBuddy\gaokao-database'

PDF_URLS = {
    2022: {
        '历史': 'https://gzzk.gz.gov.cn/attachment/7/7135/7135741/8432178.pdf',
        '物理': 'https://gzzk.gz.gov.cn/attachment/7/7135/7135742/8432178.pdf',
    },
    2023: {
        # Try to find 2023 PDF URLs
        '历史': 'https://gzzk.gz.gov.cn/attachment/7/7413/7413216/9068452.pdf',
        '物理': 'https://gzzk.gz.gov.cn/attachment/7/7413/7413217/9068452.pdf',
    }
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def download_pdf(url, year, cat):
    local_path = os.path.join(BASE_DIR, 'scripts', f'guangdong_{year}_{cat}.pdf')
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        with open(local_path, 'wb') as f:
            f.write(resp.content)
        print(f"[广东{year} {cat}] Downloaded PDF ({len(resp.content)} bytes)")
        return local_path
    except Exception as e:
        print(f"[广东{year} {cat}] Failed: {e}")
        return None

if __name__ == '__main__':
    for year in [2022, 2023]:
        for cat, url in PDF_URLS.get(year, {}).items():
            download_pdf(url, year, cat)
