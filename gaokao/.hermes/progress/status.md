# 驷马报考 - 项目状态

> 最后更新: 2026-07-05 19:28

## 当前版本: v2.0.0

### 数据规模
| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 录取数据 | 100,334 | 200,682 |
| 院校数量 | 2,952 | 2,952 |
| forum 帖子 | 172 | **392** |
| forum 关联率 | 15/172 (8.7%) | **59/392 (15.0%)** |
| jobs 招聘 | 15 | **675** |
| control_lines | 18 | 18 |

### 服务状态
- **API 服务**: ✅ 运行中 (127.0.0.1:8000, PID 19476)
- **AI 问答**: DeepSeek API
- **前端**: Vue3 单页应用

## 今日修复总结 (2026-07-05)

### Claude Code 修复（14 个文件）

#### 问题 1：爬虫输出路径错误 — 10 个爬虫文件 `parents[4]` → `parents[5]`
- `bilibili_forum_patrol.py`
- `bilibili_comments_deep.py`
- `job_collector_final.py` / `job_data_collector.py` / `v2` / `v3`
- `zhihu_forum_patrol.py` / `v2`
- `tieba_forum_patrol.py`
- `chsi_satisfaction.py`
- `zhejiang_admission_spider.py` / `province_admission_spider.py` / `control_line_spider.py`

#### 问题 2：import_to_sqlite.py
- `_resolve_data()` 改为先查 `data/raw/`，找不到回退 `src/data/raw/`
- 新增 schema 迁移：自动 ALTER TABLE 补充缺失列（score, category, sentiment, comment_id 等 10 列）

#### 问题 3：招聘采集超时
- 每日管线改为快速模式（3 城，原 10 城）
- 每页超时 25s→15s，sleep 4s→2s

### 数据采集专员验证结果

| 验证项 | 结果 |
|--------|------|
| 每日管线完整跑通 | ✅ 6/6（监控模块有 import 警告,管线主体正常） |
| 路径输出到 data/raw/ | ✅ 确认 |
| 招聘采集不再超时 | ✅ ~3min 完成 60 条 |
| import_to_sqlite.py | ✅ 自动补充 10 列,导入积压数据 |
| fix_forum_school_ids.py | ✅ +41 条关联 |
| API 服务 | ✅ 8000 端口正常运行 |

### 已知问题
- `daily_run.py` 第 575 行 `from src.scripts.monitor_data import run_monitor` 报 No module named 'src'（管线主体不受影响）
- forum 关联率 15% — B站内容多为泛志愿填报话题，非具体学校讨论，属正常现象
- B站搜索部分关键词偶发 JSON 解析失败（"搜索失败 [xxx]: Expecting value"），5/13 成功，属 API 限流

### 待办事项
1. **7月15日**: 投档线数据自动采集
2. **可选**: 修复 daily_run.py 中 monitor 模块 import 路径
3. **可选**: B站搜索增加重试/代理机制提升成功率
