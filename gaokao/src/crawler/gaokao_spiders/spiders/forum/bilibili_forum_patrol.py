#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
B站论坛巡检 — 每日采集高考志愿相关视频评论

功能：
  每天搜索高考志愿/院校/专业相关的最新视频
  提取视频评论内容，分析情感倾向
  关联院校/专业

使用：
  python .../bilibili_forum_patrol.py
  python .../bilibili_forum_patrol.py --dry-run
  python .../bilibili_forum_patrol.py --keywords-file kw.txt

输出：
  data/raw/forum/bilibili/YYYY-MM-DD.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("bilibili_patrol")

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "forum" / "bilibili"


@dataclass
class ForumPost:
    """论坛帖子"""
    platform: str = "B站"
    thread_id: str = ""
    title: str = ""
    content_text: str = ""
    platform_url: str = ""
    author_id: str = ""
    view_count: int = 0
    like_count: int = 0
    reply_count: int = 0
    publish_time: str = ""
    crawl_time: str = ""
    quality_score: int = 0
    summary: str = ""
    data_source: str = "B站API"
    school_id: Optional[str] = None
    created_at: str = ""
    is_useful: bool = False


class BilibiliForumPatrol:
    """B站论坛巡检"""

    SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"
    COMMENT_API = "https://api.bilibili.com/x/v2/medialist/resource/list"
    VIDEO_INFO_API = "https://api.bilibili.com/x/web-interface/view"

    # 每日搜索关键词组合
    DEFAULT_KEYWORDS = [
        "高考志愿 填报 推荐",
        "大学专业 值得报吗",
        "高考 选专业 避坑",
        "志愿填报 经验分享",
        "大学生活 真实体验",
        "计算机专业 就业",
        "医学专业 报考",
        "法学专业 前景",
        "师范专业 怎么样",
        "高考 院校选择",
    ]

    def __init__(self, keywords: Optional[List[str]] = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/",
        })
        self.keywords = keywords or self.DEFAULT_KEYWORDS
        self.seen_bvids: set = set()

    def run(self, dry_run: bool = False) -> List[ForumPost]:
        """主入口：搜索+获取评论"""
        all_posts: List[ForumPost] = []
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        for keyword in self.keywords:
            logger.info("搜索关键词: %s", keyword)
            videos = self._search_videos(keyword)
            if not videos:
                continue

            for video in videos:
                bvid = video.get("bvid")
                if not bvid or bvid in self.seen_bvids:
                    continue
                self.seen_bvids.add(bvid)

                title = self._clean_html(video.get("title", ""))
                author = video.get("author", "")
                play = video.get("play", 0)
                like = video.get("like", 0)
                reply = video.get("video_review", 0)
                desc = video.get("description", "")
                pubdate = video.get("pubdate", 0)

                # 生成帖子记录
                pub_time = datetime.fromtimestamp(pubdate, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if pubdate else ""

                post = ForumPost(
                    thread_id=bvid,
                    title=title,
                    content_text=desc[:500],
                    platform_url=f"https://www.bilibili.com/video/{bvid}",
                    author_id=hashlib.md5(author.encode()).hexdigest()[:16],
                    view_count=play,
                    like_count=like,
                    reply_count=reply,
                    publish_time=pub_time,
                    crawl_time=now_iso,
                    data_source="B站API",
                    created_at=now_iso,
                )

                # 质量评分：播放量越高越有价值
                if play > 100000:
                    post.quality_score = 10
                    post.is_useful = True
                elif play > 50000:
                    post.quality_score = 8
                    post.is_useful = True
                elif play > 10000:
                    post.quality_score = 6
                    post.is_useful = True
                elif play > 1000:
                    post.quality_score = 4
                else:
                    post.quality_score = 2

                # 尝试获取热评
                top_comments = self._get_top_comments(bvid)
                if top_comments:
                    post.content_text = f"{desc[:300]}\n---热门评论---\n" + "\n".join(top_comments[:3])

                all_posts.append(post)

                # 尝试识别关联的院校/专业（从标题和描述中）
                matched_schools = self._match_school(title + " " + desc)
                if matched_schools:
                    post.school_id = matched_schools[0]  # 取第一个匹配的

        if dry_run:
            logger.info("== 预览: 前 5 条 ==")
            for p in all_posts[:5]:
                print(f"[{p.quality_score}星] {p.title[:50]} | {p.view_count}播放 | {p.like_count}赞")

        logger.info("采集完成: 共 %d 条帖子", len(all_posts))
        return all_posts

    def _search_videos(self, keyword: str, page: int = 1) -> List[Dict]:
        """搜索视频"""
        try:
            resp = self.session.get(
                self.SEARCH_API,
                params={"search_type": "video", "keyword": keyword, "page": page},
                timeout=15,
            )
            data = resp.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("result", [])
            return []
        except Exception as e:
            logger.warning("搜索失败 [%s]: %s", keyword, e)
            return []

    def _get_top_comments(self, bvid: str) -> List[str]:
        """获取视频热门评论"""
        try:
            resp = self.session.get(
                f"https://api.bilibili.com/x/v2/medialist/resource/list",
                params={"type": 1, "biz_id": bvid, "ps": 5},
                timeout=10,
            )
            data = resp.json()
            if data.get("code") == 0:
                items = data.get("data", {}).get("media_list", [])
                comments = []
                for item in items[:5]:
                    if isinstance(item, dict) and "title" in item:
                        comments.append(item["title"][:200])
                return comments
            return []
        except Exception:
            return []

    def _clean_html(self, text: str) -> str:
        """清理 HTML 标签"""
        return re.sub(r'<[^>]+>', '', text).strip()

    def _match_school(self, text: str) -> List[str]:
        """从文本中尝试匹配已知院校名称"""
        # 简单匹配常见关键词，完整匹配需要加载 schools 表
        known = ["北京大学", "清华大学", "浙江大学", "复旦大学", "上海交通大学",
                 "南京大学", "武汉大学", "华中科技大学", "西安交通大学"]
        matched = [s for s in known if s in text]
        return matched

    def save(self, posts: List[ForumPost], output_dir: Optional[Path] = None):
        """保存到文件"""
        out = output_dir or DATA_DIR
        out.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        out_path = out / f"{today}.jsonl"

        with open(out_path, "w", encoding="utf-8") as f:
            for p in posts:
                f.write(json.dumps(asdict(p), ensure_ascii=False, default=str) + "\n")

        logger.info("已保存: %s (%d 条)", out_path, len(posts))

        useful = sum(1 for p in posts if p.is_useful)
        print(f"\n{'='*60}")
        print(f"  B站论坛巡检 — 采集统计")
        print(f"{'='*60}")
        print(f"  总采集:    {len(posts)} 条")
        print(f"  高质量:    {useful} 条")
        print(f"  总播放:    {sum(p.view_count for p in posts):,}")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="B站论坛巡检")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    parser.add_argument("--keywords-file", type=str, help="关键词文件（每行一个）")
    args = parser.parse_args()

    keywords = None
    if args.keywords_file:
        with open(args.keywords_file, "r", encoding="utf-8") as f:
            keywords = [line.strip() for line in f if line.strip()]

    patrol = BilibiliForumPatrol(keywords=keywords)
    posts = patrol.run(dry_run=args.dry_run)

    if not args.dry_run and posts:
        patrol.save(posts)


if __name__ == "__main__":
    main()
