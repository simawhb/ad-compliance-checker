#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
知乎论坛巡检 v2 — 通过公开可访问的知乎专栏/问题页面采集

避开知乎搜索API（反爬严格），改为：
1. 直接访问已知的高考志愿相关知乎问题（URL已知）
2. 通过知乎专栏 RSS/公开页面获取
3. 采用随机 UA + 可控频率

使用：
  python .../zhihu_forum_patrol_v2.py
  python .../zhihu_forum_patrol_v2.py --dry-run

输出：
  data/raw/forum/zhihu/YYYY-MM-DD.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
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
logger = logging.getLogger("zhihu_v2")

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "forum" / "zhihu"


@dataclass
class ZhihuPostV2:
    platform: str = "知乎"
    thread_id: str = ""
    title: str = ""
    content_text: str = ""
    platform_url: str = ""
    like_count: int = 0
    reply_count: int = 0
    quality_score: int = 0
    source: str = ""
    publish_time: str = ""
    crawl_time: str = ""
    created_at: str = ""


class ZhihuPatrolV2:
    """知乎论坛巡检 v2"""

    # 已知的高考志愿热门问题（可以直接访问，无需搜索）
    KNOWN_QUESTIONS: List[dict] = [
        {"id": "19559579", "title": "高考志愿填报，你有哪些经验和建议？"},
        {"id": "35603849", "title": "高考志愿填报专业选择有什么建议？"},
        {"id": "268667870", "title": "计算机专业真的如此美好吗？"},
        {"id": "380630431", "title": "2022高考志愿填报，有哪些坑需要避免？"},
        {"id": "621019296", "title": "高考志愿填报，什么专业就业前景好？"},
        {"id": "267624589", "title": "大学选错专业是一种什么体验？"},
        {"id": "337200218", "title": "高考志愿填报，城市、学校、专业如何排序？"},
        {"id": "389490653", "title": "2023高考志愿填报，有哪些热门专业推荐？"},
        {"id": "625736157", "title": "高考报志愿，张雪峰的建议真的有用吗？"},
        {"id": "407616724", "title": "法学专业就业前景如何？"},
        {"id": "301881495", "title": "医学专业前景如何？临床医学值得读吗？"},
        {"id": "369735284", "title": "师范类专业未来就业前景如何？"},
        {"id": "19843489", "title": "大学本科专业选择，应该以兴趣为主还是以就业前景为主？"},
    ]

    # PC 和 Mobile UA 随机池
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    ]

    def __init__(self):
        self.session = requests.Session()
        self._rotate_ua()

    def _rotate_ua(self):
        """随机切换 UA"""
        ua = random.choice(self.USER_AGENTS)
        self.session.headers.update({
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.zhihu.com/",
        })

    def run(self, dry_run: bool = False) -> List[ZhihuPostV2]:
        """采集知乎热门问题下的回答"""
        all_posts: List[ZhihuPostV2] = []
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 随机打乱问题顺序
        questions = self.KNOWN_QUESTIONS.copy()
        random.shuffle(questions)

        for q in questions[:7]:  # 每次只采前7个（控制频率）
            posts = self._scrape_question(q["id"], q["title"])
            all_posts.extend(posts)
            # 每次请求间隔 8-15 秒（反爬保护）
            delay = random.uniform(8, 15)
            logger.debug("等待 %.1f 秒...", delay)
            time.sleep(delay)

        for p in all_posts:
            p.crawl_time = now_iso
            p.created_at = now_iso

        if dry_run:
            logger.info("== 预览: 前 5 条 ==")
            for p in all_posts[:5]:
                print(f"  [{p.like_count}赞] {p.title[:60]}")

        logger.info("采集完成: %d 条", len(all_posts))
        return all_posts

    def _scrape_question(self, qid: str, title: str) -> List[ZhihuPostV2]:
        """抓取单个知乎问题页面的回答"""
        posts: List[ZhihuPostV2] = []

        # 知乎问题页面URL
        url = f"https://www.zhihu.com/question/{qid}"

        try:
            self._rotate_ua()  # 每次请求切换UA
            resp = self.session.get(url, timeout=15)

            if resp.status_code != 200:
                logger.debug("问题 %s: HTTP %d", qid, resp.status_code)
                return posts

            # 尝试从页面提取回答内容
            soup = BeautifulSoup(resp.text, "html.parser")

            # 知乎SSR页面，回答可能在HTML中
            # 方法1: 找JSON-LD数据
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        desc = data.get("description", "")
                        if desc and len(desc) > 20:
                            post = ZhihuPostV2(
                                thread_id=qid,
                                title=title,
                                content_text=desc[:500],
                                platform_url=url,
                                like_count=0,
                                reply_count=0,
                                quality_score=5,
                                source="知乎问题页",
                            )
                            posts.append(post)
                except (json.JSONDecodeError, TypeError):
                    pass

            # 方法2: 找页面中的回答卡片
            cards = soup.select(".AnswerCard") or soup.select("[data-za-module='AnswerItem']")
            for card in cards[:5]:
                try:
                    text = card.get_text(strip=True)[:300]
                    vote_el = card.select_one(".Voters") or card.select_one(".zm-item-vote")
                    likes = 0
                    if vote_el:
                        likes = int(re.sub(r'\D', '', vote_el.get_text(strip=True)) or 0)

                    if len(text) > 30:
                        post = ZhihuPostV2(
                            thread_id=f"{qid}_{hashlib.md5(text[:50].encode()).hexdigest()[:8]}",
                            title=title,
                            content_text=text[:500],
                            platform_url=url,
                            like_count=likes,
                            quality_score=min(likes // 10, 10) if likes > 0 else 3,
                            source="知乎SSR",
                        )
                        posts.append(post)
                except Exception:
                    continue

            # 方法3: 从页面meta标签取值
            if not posts:
                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc and meta_desc.get("content"):
                    desc = meta_desc["content"]
                    if len(desc) > 20:
                        post = ZhihuPostV2(
                            thread_id=qid, title=title,
                            content_text=desc[:500], platform_url=url,
                            quality_score=3, source="知乎meta",
                        )
                        posts.append(post)

        except requests.Timeout:
            logger.debug("问题 %s: 超时", qid)
        except Exception as e:
            logger.debug("问题 %s: %s", qid, e)

        return posts

    def save(self, posts: List[ZhihuPostV2], output_dir: Optional[Path] = None):
        out = output_dir or DATA_DIR
        out.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        out_path = out / f"{today}.jsonl"

        with open(out_path, "w", encoding="utf-8") as f:
            for p in posts:
                f.write(json.dumps(asdict(p), ensure_ascii=False, default=str) + "\n")

        logger.info("已保存: %s (%d 条)", out_path, len(posts))

        total_likes = sum(p.like_count for p in posts)
        print(f"\n{'='*60}")
        print(f"  知乎巡检 — 采集统计")
        print(f"{'='*60}")
        print(f"  总条数:    {len(posts)}")
        print(f"  总点赞:    {total_likes}")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="知乎论坛巡检 v2")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    patrol = ZhihuPatrolV2()
    posts = patrol.run(dry_run=args.dry_run)
    if not args.dry_run and posts:
        patrol.save(posts)


if __name__ == "__main__":
    main()
