#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
贴吧论坛巡检 — 每日采集各大学吧/专业吧的最新帖

百度贴吧对爬虫友好，无需登录可访问公开版面。

使用：
  python .../tieba_forum_patrol.py
  python .../tieba_forum_patrol.py --dry-run

输出：
  data/raw/forum/tieba/YYYY-MM-DD.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("tieba_patrol")

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "forum" / "tieba"


@dataclass
class TiebaPost:
    platform: str = "贴吧"
    thread_id: str = ""
    title: str = ""
    content_text: str = ""
    platform_url: str = ""
    author_id: str = ""
    reply_count: int = 0
    quality_score: int = 0
    source: str = ""
    crawl_time: str = ""
    created_at: str = ""


class TiebaForumPatrol:
    """贴吧论坛巡检"""

    # 关注的大学吧列表（首批 Top 50 + 陕西本地）
    SCHOOL_BARS = [
        # 陕西
        "西安交通大学", "西北工业大学", "西安电子科技大学", "陕西师范大学",
        "西北大学", "长安大学", "西北农林科技大学", "西安理工大学",
        "西安建筑科技大学", "陕西科技大学", "西安科技大学", "西安外国语大学",
        "西北政法大学", "西安邮电大学", "西安工业大学",
        # Top 综合
        "北京大学", "清华大学", "浙江大学", "复旦大学", "上海交通大学",
        "南京大学", "武汉大学", "华中科技大学", "中山大学", "四川大学",
        "哈尔滨工业大学", "北京航空航天大学", "同济大学", "南开大学",
        # 专业特色
        "北京邮电大学", "电子科技大学", "中国政法大学", "中央财经大学",
        "上海财经大学", "对外经济贸易大学", "北京外国语大学", "中国传媒大学",
    ]

    # 专业吧列表
    MAJOR_BARS = [
        "计算机", "软件工程", "电子信息", "土木工程", "机械",
        "会计", "金融", "法学", "医学", "师范",
        "高考", "高考志愿", "考研",
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
        })

    def run(self, dry_run: bool = False) -> List[TiebaPost]:
        """主入口"""
        all_posts: List[TiebaPost] = []
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 每天跑一半的学校吧（轮流，避免频率过高）
        bars_to_scan = self.SCHOOL_BARS[:15] if dry_run else self.SCHOOL_BARS[:20]
        bars_to_scan += self.MAJOR_BARS[:5]

        for bar_name in bars_to_scan:
            try:
                posts = self._scrape_bar(bar_name)
                all_posts.extend(posts)
            except Exception as e:
                logger.debug("贴吧[%s]: %s", bar_name, e)

        for p in all_posts:
            p.crawl_time = now_iso
            p.created_at = now_iso

        if dry_run:
            logger.info("== 预览: 前 5 条 ==")
            for p in all_posts[:5]:
                print(f"  [{p.reply_count}回复] {p.title[:60]}")

        logger.info("采集完成: %d 条, 覆盖 %d 个贴吧",
                     len(all_posts), len(bars_to_scan))
        return all_posts

    def _scrape_bar(self, bar_name: str) -> List[TiebaPost]:
        """采集单个贴吧的帖子列表"""
        posts: List[TiebaPost] = []

        url = f"https://tieba.baidu.com/f?kw={bar_name}&ie=utf-8"
        resp = self.session.get(url, timeout=10)

        if resp.status_code != 200:
            return posts

        soup = BeautifulSoup(resp.text, "html.parser")

        # 找帖子列表
        threads = (
            soup.select(".j_thread_list")
            or soup.select("li.j_thread_list")
            or soup.select(".threadlist_title a")
        )

        if not threads:
            # fallback: 找所有带 href 的链接
            threads = soup.select("a[href*='/p/']")

        seen = set()
        for thread in threads[:20]:
            try:
                # 提取标题和链接
                a_tag = None
                if thread.name == "a":
                    a_tag = thread
                else:
                    a_tag = thread.select_one("a") or thread

                if not a_tag:
                    continue

                href = a_tag.get("href", "")
                title = a_tag.get("title", "") or a_tag.get_text(strip=True)

                if not title or not href:
                    continue

                # 提取帖子ID
                tid_match = re.search(r'/p/(\d+)', href)
                tid = tid_match.group(1) if tid_match else hashlib.md5(href.encode()).hexdigest()[:12]

                if tid in seen:
                    continue
                seen.add(tid)

                # 完整URL
                full_url = f"https://tieba.baidu.com/p/{tid}" if tid_match else href

                # 提取回复数
                reply_el = thread.select_one(".threadlist_rep") or thread.select_one(".reply")
                replies = 0
                if reply_el:
                    try:
                        replies = int(reply_el.get_text(strip=True))
                    except ValueError:
                        pass

                # 只收录与高考/志愿/专业相关的内容
                keywords = ["高考", "志愿", "专业", "就业", "录取", "分数",
                            "宿舍", "校区", "毕业", "考研", "排名", "怎么样"]
                has_kw = any(kw in title for kw in keywords)

                if not has_kw and replies < 5:
                    continue

                quality = min(replies, 10)
                post = TiebaPost(
                    thread_id=tid,
                    title=title[:200],
                    content_text=f"[{bar_name}吧] {title}",
                    platform_url=full_url,
                    reply_count=replies,
                    quality_score=quality,
                    source=f"贴吧-{bar_name}",
                )
                posts.append(post)

            except Exception:
                continue

        return posts

    def save(self, posts: List[TiebaPost], output_dir: Optional[Path] = None):
        out = output_dir or DATA_DIR
        out.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        out_path = out / f"{today}.jsonl"

        with open(out_path, "w", encoding="utf-8") as f:
            for p in posts:
                f.write(json.dumps(asdict(p), ensure_ascii=False, default=str) + "\n")

        logger.info("已保存: %s (%d 条)", out_path, len(posts))

        total_replies = sum(p.reply_count for p in posts)
        print(f"\n{'='*60}")
        print(f"  贴吧巡检 — 采集统计")
        print(f"{'='*60}")
        print(f"  总条数:    {len(posts)}")
        print(f"  总回复数:  {total_replies}")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="贴吧论坛巡检")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    patrol = TiebaForumPatrol()
    posts = patrol.run(dry_run=args.dry_run)
    if not args.dry_run and posts:
        patrol.save(posts)


if __name__ == "__main__":
    main()
