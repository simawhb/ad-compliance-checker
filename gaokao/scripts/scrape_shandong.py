#!/usr/bin/env python3
"""Scrape Shandong 2022 & 2023 admission data from sdzk.cn XLS files"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
import urllib.parse

BASE_DIR = r'D:\WorkBuddy\gaokao-database'

# The Shandong pages link to XLS files - we can try to parse the XLS
# But first let's check what's available on the page
NEWS_IDS = {
    2023: 6279,  # 山东省2023年普通类常规批第1次志愿投档情况表
    2022: 5846,  # 山东省2022年普通类常规批第1次志愿投档情况表
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def scrape_shandong_page(year):
    """Scrape the Shandong page to find the XLS download link"""
    news_id = NEWS_IDS[year]
    url = f'https://www.sdzk.cn/NewsInfo.aspx?NewsID={news_id}'
    
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.encoding = 'utf-8'
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Find all links
    links = soup.find_all('a')
    xls_url = None
    for link in links:
        href = link.get('href', '')
        if '.xls' in href.lower() or '.xlsx' in href.lower():
            if not href.startswith('http'):
                # Relative URL
                xls_url = urllib.parse.urljoin(url, href)
            else:
                xls_url = href
            print(f"[山东{year}] Found XLS link: {xls_url}")
            break
    
    if not xls_url:
        print(f"[山东{year}] No XLS link found on page")
        # Try to find any download links
        for link in links:
            href = link.get('href', '')
            if 'Floadup' in href:
                print(f"  Found Floadup link: {href}")
    
    return xls_url

def download_xls(url, year):
    """Download XLS file"""
    if not url:
        return None
    
    local_path = os.path.join(BASE_DIR, 'scripts', f'shandong_{year}.xls')
    resp = requests.get(url, headers=HEADERS, timeout=60)
    with open(local_path, 'wb') as f:
        f.write(resp.content)
    print(f"[山东{year}] Downloaded XLS ({len(resp.content)} bytes) to {local_path}")
    return local_path

if __name__ == '__main__':
    for year in [2022, 2023]:
        xls_url = scrape_shandong_page(year)
        if xls_url:
            download_xls(xls_url, year)
