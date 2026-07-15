#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
B站评论深度采集 — 从已采集视频中提取详细评论

对B站巡检中采集到的视频，进一步获取评论区内容
用于口碑情感分析和关键词提取

使用：
  python .../bilibili_comments_deep.py
  python .../bilibili_comments_deep.py --dry-run

输出：
  data/raw/forum/bilibili/comments_YYYY-MM-DD.jsonl
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("bili_comments")

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "forum" / "bilibili"
FORUM_DIR = PROJECT_ROOT / "data" / "raw" / "forum" / "bilibili"


@dataclass
class Comment:
    platform: str = "B站"
    thread_id: str = ""
    comment_id: str = ""
    content_text: str = ""
    like_count: int = 0
    reply_count: int = 0
    sentiment: str = ""  # positive/negative/neutral
    author_id: str = ""
    platform_url: str = ""
    publish_time: str = ""
    crawl_time: str = ""
    data_source: str = "B站评论API"
    created_at: str = ""


class BilibiliCommentCollector:
    """B站评论深度采集"""

    COMMENT_API = "https://api.bilibili.com/x/v2/medialist/resource/list"
    REPLY_API = "https://api.bilibili.com/x/v2/reply"

    def __init__(self, max_videos: int = 10):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com/",
        })
        self.max_videos = max_videos

    def run(self, dry_run: bool = False) -> List[Comment]:
        """从当天B站巡检数据中取评论"""
        all_comments: List[Comment] = []
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 读取当天B站巡检结果
        today = datetime.now().strftime("%Y-%m-%d")
        forum_file = FORUM_DIR / f"{today}.jsonl"

        if not forum_file.exists():
            logger.warning("今日B站巡检数据不存在: %s", forum_file)
            return all_comments

        # 读取所有视频BV号
        bvids = []
        with open(forum_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    post = json.loads(line)
                    tid = post.get("thread_id", "")
                    if tid and tid.startswith("BV"):
                        bvids.append(tid)
                except json.JSONDecodeError:
                    continue

        # 去重
        bvids = list(set(bvids))
        logger.info("今日有 %d 个视频，开始采集评论...", len(bvids))

        # 对每个视频取评论
        for bvid in bvids[:self.max_videos]:
            comments = self._get_comments(bvid)
            for c in comments:
                c.crawl_time = now_iso
                c.created_at = now_iso
            all_comments.extend(comments)

            if dry_run and len(all_comments) >= 20:
                break

            time.sleep(0.5)  # 礼貌间隔

        if dry_run:
            logger.info("== 预览: 前5条评论 ==")
            for c in all_comments[:5]:
                print(f"  [{c.like_count}赞] {c.content_text[:60]}...")

        logger.info("采集完成: %d 条评论, 来自 %d 个视频", len(all_comments), min(len(bvids), self.max_videos))
        return all_comments

    def _get_comments(self, bvid: str) -> List[Comment]:
        """获取单个视频的评论"""
        comments: List[Comment] = []

        try:
            resp = self.session.get(
                "https://api.bilibili.com/x/v2/reply",
                params={"type": 1, "oid": bvid, "sort": 2, "ps": 20, "pn": 1},
                timeout=15,
            )
            data = resp.json()
            if data.get("code") != 0:
                # 用oid方式重试 — 先获取oid
                return self._get_comments_by_aid(bvid)

            replies = data.get("data", {}).get("replies", [])
            for reply in replies[:20]:
                try:
                    content = reply.get("content", {}).get("message", "")
                    if not content or len(content) < 5:
                        continue

                    like = reply.get("like", 0)
                    rcount = reply.get("rcount", 0)
                    mid = reply.get("mid", 0)
                    rpid = reply.get("rpid", 0)
                    ctime = reply.get("ctime", 0)

                    # 简单情感判断
                    sentiment = self._guess_sentiment(content)

                    comment = Comment(
                        thread_id=bvid,
                        comment_id=str(rpid),
                        content_text=content[:300],
                        like_count=like,
                        reply_count=rcount,
                        sentiment=sentiment,
                        author_id=hashlib.md5(str(mid).encode()).hexdigest()[:12],
                        platform_url=f"https://www.bilibili.com/video/{bvid}",
                    )
                    comments.append(comment)
                except Exception:
                    continue

        except Exception as e:
            logger.debug("视频 %s 评论获取失败: %s", bvid, e)

        return comments

    def _get_comments_by_aid(self, bvid: str) -> List[Comment]:
        """通过aid获取评论（备选方式）"""
        comments: List[Comment] = []
        try:
            # 先获取aid
            info_resp = self.session.get(
                f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
                timeout=10,
            )
            info = info_resp.json()
            aid = info.get("data", {}).get("aid", 0)
            if not aid:
                return comments

            resp = self.session.get(
                "https://api.bilibili.com/x/v2/reply",
                params={"type": 1, "oid": aid, "sort": 2, "ps": 20, "pn": 1},
                timeout=15,
            )
            data = resp.json()
            if data.get("code") != 0:
                return comments

            replies = data.get("data", {}).get("replies", [])
            for reply in replies[:20]:
                try:
                    content = reply.get("content", {}).get("message", "")
                    if not content or len(content) < 5:
                        continue
                    comment = Comment(
                        thread_id=bvid,
                        comment_id=str(reply.get("rpid", 0)),
                        content_text=content[:300],
                        like_count=reply.get("like", 0),
                        reply_count=reply.get("rcount", 0),
                        sentiment=self._guess_sentiment(content),
                        author_id=hashlib.md5(str(reply.get("mid", 0)).encode()).hexdigest()[:12],
                        platform_url=f"https://www.bilibili.com/video/{bvid}",
                    )
                    comments.append(comment)
                except Exception:
                    continue
        except Exception:
            pass
        return comments

    @staticmethod
    def _guess_sentiment(text: str) -> str:
        """简单情感判断"""
        positive = ["好", "棒", "推荐", "不错", "值得", "有用", "厉害", "感谢", "赞", "牛", "强",
                     "喜欢", "可以", "靠谱", "良心", "收藏", "干货", "实用", "666", "支持"]
        negative = ["坑", "别去", "垃圾", "后悔", "不好", "骗人", "没用", "差", "水", "避雷",
                     "劝退", "慎重", "别报", "慎重", "拉胯", "失望"]
        text_lower = text.lower()
        pos_count = sum(1 for w in positive if w in text_lower)
        neg_count = sum(1 for w in negative if w in text_lower)
        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        return "neutral"

    def save(self, comments: List[Comment]):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        path = DATA_DIR / f"comments_{today}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for c in comments:
                f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
        logger.info("已保存: %s (%d 条)", path, len(comments))

        pos = sum(1 for c in comments if c.sentiment == "positive")
        neg = sum(1 for c in comments if c.sentiment == "negative")
        print(f"\n{'='*60}")
        print(f"  B站评论深度采集 — 统计")
        print(f"{'='*60}")
        print(f"  总评论:   {len(comments)}")
        print(f"  正面:     {pos} ({round(pos/len(comments)*100,1) if comments else 0}%)")
        print(f"  负面:     {neg} ({round(neg/len(comments)*100,1) if comments else 0}%)")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="B站评论深度采集")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-videos", type=int, default=10, help="最多采集视频数")
    args = parser.parse_args()

    c = BilibiliCommentCollector(max_videos=args.max_videos)
    comments = c.run(dry_run=args.dry_run)
    if not args.dry_run and comments:
        c.save(comments)


if __name__ == "__main__":
    main()
