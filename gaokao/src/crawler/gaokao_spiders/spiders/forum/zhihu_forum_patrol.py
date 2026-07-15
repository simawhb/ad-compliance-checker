#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
知乎论坛巡检 — 每日采集高考志愿相关问答

使用知乎搜索公开页面。
注意：知乎反爬较严，频率控制需保守。

使用：
  python .../zhihu_forum_patrol.py
  python .../zhihu_forum_patrol.py --dry-run

输出：
  data/raw/forum/zhihu/YYYY-MM-DD.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import time
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
logger = logging.getLogger("zhihu_patrol")

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "forum" / "zhihu"


@dataclass
class ZhihuPost:
    platform: str = "知乎"
    thread_id: str = ""
    title: str = ""
    content_text: str = ""
    platform_url: str = ""
    author_id: str = ""
    like_count: int = 0
    reply_count: int = 0
    publish_time: str = ""
    crawl_time: str = ""
    summary: str = ""
    data_source: str = "知乎搜索"
    created_at: str = ""
    quality_score: int = 0


class ZhihuForumPatrol:
    """知乎论坛巡检"""

    SEARCH_URL = "https://www.zhihu.com/search"

    DEFAULT_QUESTIONS = [
        "在XX大学就读是什么体验",
        "计算机专业 就业前景",
        "高考志愿 怎么选专业",
        "大学专业 避雷 指南",
        "XX专业 值得读吗",
        "高考 填报志愿 经验",
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })

    def run(self, dry_run: bool = False) -> List[ZhihuPost]:
        """采集知乎高考志愿相关内容"""
        all_posts: List[ZhihuPost] = []
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        for question in self.DEFAULT_QUESTIONS:
            try:
                posts = self._search(question)
                all_posts.extend(posts)
                time.sleep(5)  # 知乎反爬严，每次请求间隔5秒
            except Exception as e:
                logger.warning("搜索失败 [%s]: %s", question, e)
                continue

        # 补全时间戳
        for p in all_posts:
            p.crawl_time = now_iso
            p.created_at = now_iso

        if dry_run:
            logger.info("== 预览: 前 5 条 ==")
            for p in all_posts[:5]:
                print(f"  [{p.like_count}赞] {p.title[:60]}")

        logger.info("采集完成: %d 条", len(all_posts))
        return all_posts

    def _search(self, keyword: str) -> List[ZhihuPost]:
        """搜索知乎内容"""
        posts: List[ZhihuPost] = []

        try:
            resp = self.session.get(
                self.SEARCH_URL,
                params={"type": "content", "q": keyword},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning("知乎搜索返回 %d", resp.status_code)
                return posts
        except Exception as e:
            logger.warning("知乎搜索请求失败: %s", e)
            return posts

        # 知乎页面是SSR，尝试解析
        soup = BeautifulSoup(resp.text, "html.parser")

        # 找搜索结果卡片
        cards = (
            soup.select(".SearchResult-Card")
            or soup.select(".ContentItem")
            or soup.select("article")
        )

        for card in cards[:10]:  # 每页最多取10条
            try:
                title_el = card.select_one("a[href*='question']") or card.select_one("h2 a")
                if not title_el:
                    continue

                href = title_el.get("href", "")
                title = title_el.get_text(strip=True)

                # 提取ID
                qid_match = re.search(r'/question/(\d+)', href)
                tid = qid_match.group(1) if qid_match else hashlib.md5(href.encode()).hexdigest()[:12]

                # 提取赞同数
                vote_el = card.select_one(".VoteButton") or card.select_one(".zm-item-vote")
                votes = 0
                if vote_el:
                    try:
                        votes = int(vote_el.get_text(strip=True))
                    except ValueError:
                        pass

                post = ZhihuPost(
                    thread_id=tid,
                    title=title[:200],
                    platform_url=f"https://www.zhihu.com/question/{tid}" if qid_match else href,
                    like_count=votes,
                    data_source="知乎搜索",
                )
                if votes > 100:
                    post.quality_score = 8
                elif votes > 10:
                    post.quality_score = 5
                else:
                    post.quality_score = 2

                posts.append(post)
            except Exception as e:
                continue

        return posts

    def save(self, posts: List[ZhihuPost], output_dir: Optional[Path] = None):
        out = output_dir or DATA_DIR
        out.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        out_path = out / f"{today}.jsonl"

        with open(out_path, "w", encoding="utf-8") as f:
            for p in posts:
                f.write(json.dumps(asdict(p), ensure_ascii=False, default=str) + "\n")

        logger.info("已保存: %s (%d 条)", out_path, len(posts))


def main():
    parser = argparse.ArgumentParser(description="知乎论坛巡检")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    patrol = ZhihuForumPatrol()
    posts = patrol.run(dry_run=args.dry_run)
    if not args.dry_run and posts:
        patrol.save(posts)


if __name__ == "__main__":
    main()
