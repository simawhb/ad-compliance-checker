# 驷马报考 — 项目手册

> **项目名称：** 驷马报考
> **目标：** 用 6-12 个月构建覆盖全国的高考志愿填报数据库，最终形态（小程序/网页/API）后续决定
> **核心理念：** 日拱一卒，数据日积月累；矛盾数据展示给用户自己判断

---

## 项目定位

驷马报考的差异化价值在于三个"结合"：

1. **官方数据 + 用户口碑交叉验证** —— 录取分数线是客观的，但专业的"真实体验"要看论坛
2. **地域招聘 × 专业关联** —— 一个专业在不同城市的就业机会天差地别，用招聘大数据说话
3. **矛盾数据不掩盖，展示给用户看** —— 同一个专业，有人说好有人说坏，都呈现，让用户自己判断

---

## 一、数据源全景与采集频率矩阵

我将所有数据源按**采集频率**分成 4 个级别：

| 级别 | 频率 | 说明 | 适用数据 |
|------|------|------|---------|
| **D** | Daily（每日） | 轻量级巡检+增量采集 | 论坛新帖、招聘数据、监控改版 |
| **W** | Weekly（每周） | 批量、稳定更新 | 排名变化、就业报告新增 |
| **M** | Monthly（每月） | 非紧急的深度采集 | UGC口碑数据、省份分爬 |
| **S** | Seasonal（季度/年度） | 特定时间窗口批量跑 | 录取数据、政策文件、院校名单 |

具体分配如下：

### 📅 Daily 每日任务

```
(1) 论坛舆情巡检（轻量级）
├── B站：搜索"xx大学 xx专业 值得报吗"最新视频 → 爬评论区
├── 知乎：新提问监控（关键词："xx大学 怎么样"、"xx专业 就业"）
└── 贴吧：各大学吧的新帖检查
└── 产出：当日新增论坛帖 → 入 user_reviews 暂存区

(2) 招聘数据采集（轻量级）
├── BOSS直聘公开数据：按城市+专业关键词搜索岗位数
├── 智联招聘公开数据：同上
├── 产出：每个城市下各专业的岗位数量、薪资范围 → 入 employment_stats
└── 注意：只统计公开搜索可见的岗位数量，不碰个人简历

(3) 数据巡检
├── 检查已采集的考试院URL是否仍然可访问（改版检测）
├── 检查已采集的PDF链接是否仍然有效
└── 产出：变更告警（有改版就通知）
```

### 📅 Weekly 每周任务

```
(1) 院校数据补充
├── 每周做 1-2 个省份的院校详细信息采集
├── 从阳光高考补充：学费、宿舍条件、招生章程
└── 预计耗时：1-2小时/周

(2) 排名数据
├── 检查软科/校友会是否有新排名发布
├── 如有，启动采集脚本
└── 预计耗时：30分钟/周

(3) 周报生成
├── 统计本周新增数据量
├── 列出异常数据和待处理事项
└── 产出：周报保存到 reports/weekly/
```

### 📅 Monthly 每月任务

```
(1) 省份考试院数据（按省份分月）
├── 每个月攻克 2-3 个省份的录取数据
├── 优先顺序：5月-8月集中做录取 → 其余月份做其他省份
└── 预计：每月 2-3 省 × 近 3 年数据

(2) UGC口碑批量采集
├── 知乎：批量搜索院校×专业关键词组合
├── B站：批量搜索院校×专业关键词组合
├── 小红书：谨慎的定时批采（频率控制）
└── 预计耗时：约 5-10 小时/月

(3) 数据质量检查
├── 运行全表数据校验
├── 找出一致性问题、冲突数据
└── 产出：质量月报
```

### 📅 Seasonal 季节性任务

```
(1) 5月-6月（录取数据窗口）
├── 省控线监控（6月23-26日集中采）
├── 一分一段表监控
└── 这两个窗口非常短，错过等一年

(2) 6月-8月（投档线窗口）
├── 各省陆续公布投档线
├── 按 A组→B组→C组 顺序跑
└── 这是全年最核心的采集窗口

(3) 10月-12月（就业报告窗口）
├── 各高校发布年度就业质量报告
├── 批量下载PDF → LLM提取结构化数据
└── 年度一次，优先做 Top 200 高校

(4) 4月-5月（政策窗口）
├── 各省发布年度招生工作规定
├── 教育部发布年度招生通知
└── 政策变化追踪
```

---

## 二、目录结构

```
D:\WorkBuddy\gaokao-database\
│
├── PLAN.md                         # 策划方案（已有）
├── RULES.md                        # 执行规则（已有）
├── README.md                       # 项目简介
│
├── data\                           # 数据存储
│   ├── raw\                        # 原始采集数据（.jsonl）
│   │   ├── daily\                  # 每日增量（论坛/招聘）
│   │   ├── weekly\                 # 每周批量
│   │   ├── monthly\                # 每月深度采集
│   │   └── seasonal\               # 季节性批量
│   ├── processed\                  # 清洗后数据（待入库）
│   ├── attachments\                # PDF/图片附件
│   └── exports\                    # 数据导出
│
├── reports\                        # 数据报告
│   ├── daily\                      # 每日简报
│   ├── weekly\                     # 每周汇报
│   └── monthly\                    # 质量月报
│
├── logs\                           # 运行日志
│
├── src\                            # 源代码
│   ├── crawler\                    # Scrapy 爬虫项目
│   │   └── gk_crawler\
│   │       └── spiders\
│   │           ├── daily\          # 每日爬虫
│   │           ├── weekly\         # 每周爬虫
│   │           ├── monthly\        # 每月爬虫
│   │           └── seasonal\       # 季节性爬虫
│   ├── etl\                        # 数据 ETL 管线
│   │   ├── data_validator.py       # 校验模块
│   │   ├── data_loader.py          # 导入模块
│   │   └── pdf_parser.py           # PDF 解析
│   ├── analysis\                   # 数据分析
│   │   ├── sentiment.py            # 情感分析
│   │   ├── cross_validate.py       # 跨平台交叉验证
│   │   └── regional_job.py         # 地域招聘分析
│   ├── monitor\                    # 监控
│   │   ├── site_checker.py         # 网站改版检测
│   │   └── reporter.py             # 报告生成
│   └── scripts\                    # 运维脚本
│       ├── init_db.sql
│       └── daily_run.py            # 每日运行入口
│
└── .hermes\
    └── plans\                      # 阶段性计划
```

---

## 三、每日运行管线

这是每日自动运行的 "日报线"：

```
┌─ 每天早上: --------------------------------┐
│                                             │
│  DailyRun (daily_run.py)                    │
│  ├── 1. 检查各目标网站是否可访问              │
│  ├── 2. 论坛巡检（B站API + 知乎+贴吧）       │
│  ├── 3. 招聘数据采集（BOSS直聘+智联）        │
│  ├── 4. 清洗+校验当日采集数据                │
│  ├── 5. 数据入库                            │
│  ├── 6. 生成当日简报                        │
│  └── 7. 输出到 reports/daily/               │
│                                             │
└─────────────────────────────────────────────┘
```

### 3.1 论坛巡检详细设计

**目标：** 每天发现最新的院校/专业评价内容，持续积累口碑库。

**关键词组合策略：**

```
搜索模板（每天自动生成）：
  1. "{院校名} {专业名} 怎么样"
  2. "{院校名} {专业名} 值得"
  3. "{院校名} 避雷"
  4. "{专业名} 就业"
  5. "高考志愿 {专业名}"

执行顺序（按优先级）：
  第1步：B站 API 搜索（最安全，不需代理）
  第2步：知乎搜索公开页面
  第3步：贴吧搜索（低风险）
  第4步：小红书（仅在月集中任务中执行，不做每日）

分步覆盖策略：
  前 1-2 周：只跑 Top 50 高校（覆盖大部分搜索需求）
  第 3-8 周：扩展到 Top 200 高校
  之后：按需扩展
```

**增量去重逻辑：**
```
  每次采集前，从数据库中拉取已有的 platform_url 列表
  用 Redis 布隆过滤器或数据库 IN 查询判断是否已采集
  新内容才写入，重复的不采集
  避免同一篇帖子被反复收录
```

### 3.2 招聘数据采集详细设计

**目标：** 建立 「专业 × 城市 × 薪资/岗位数」 的关联数据库。

**招聘平台采集（公开数据层面）：**

```
采集内容：
  每个城市 × 每个关键词组合：
  - 总岗位数
  - 薪资范围（最低/平均/最高）
  - 岗位名称分布 top10
  - 学历要求分布
  - 经验要求分布

关键词映射（专业→搜索关键词）：
  计算机科学与技术 → ["Java开发", "Python", "算法工程师", "软件开发"]
  会计学             → ["财务", "会计", "审计"]
  法学               → ["法务", "律师", "法律顾问"]
  ... 逐步建立映射表

城市范围（分阶段）：
  Phase 1: 新一线城市（成都、杭州、武汉、西安、南京、重庆、苏州、长沙、郑州、合肥）
  Phase 2: 一线城市（北京、上海、广州、深圳）+ 所有省会城市
  Phase 3: 主要地级市（GDP 前 100）

注意：只统计搜索结果的数量，不抓取单个职位详情，合规可行。
```

---

## 四、数据库设计（面向"驷马报考"产品）

在 PLAN.md 的数据库设计基础上，增加两个关键表：

### 新增表：口碑差异指数

```sql
-- user_content.reputation_score
-- 每个院校 × 专业的"口碑综合得分"
CREATE TABLE user_content.reputation_score (
    id SERIAL PRIMARY KEY,
    school_id VARCHAR(10) NOT NULL,
    major_id VARCHAR(20) NOT NULL,
    year INTEGER NOT NULL DEFAULT 2026,
    -- 综合数据
    total_mentions INTEGER DEFAULT 0,        -- 总提及数（所有平台）
    positive_count INTEGER DEFAULT 0,         -- 正面评价数
    negative_count INTEGER DEFAULT 0,         -- 负面评价数
    neutral_count INTEGER DEFAULT 0,          -- 中性评价数
    sentiment_score NUMERIC(4,2),             -- 情感综合分（-1 ~ 1）
    -- 平台明细 (JSON)
    platform_breakdown JSONB,                 -- 各平台的统计
    -- 高频关键词
    positive_keywords TEXT[],                  -- 高频正面词
    negative_keywords TEXT[],                  -- 高频负面词
    -- 可信度
    confidence VARCHAR(10) DEFAULT 'low',     -- high/medium/low
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE (school_id, major_id, year)
);
```

### 新增表：地域招聘 × 专业关联

```sql
-- employment.regional_job_stats
-- 每个城市 × 专业的招聘数据统计
CREATE TABLE employment.regional_job_stats (
    id SERIAL PRIMARY KEY,
    major_id VARCHAR(20),
    major_name VARCHAR(100),
    city VARCHAR(50) NOT NULL,
    province VARCHAR(20) NOT NULL,
    year INTEGER NOT NULL DEFAULT 2026,
    month INTEGER NOT NULL DEFAULT 1,
    -- 岗位数据
    total_job_count INTEGER,                  -- 总岗位数
    avg_salary NUMERIC(8,2),                  -- 平均薪资（元/月）
    median_salary NUMERIC(8,2),               -- 薪资中位数
    salary_min NUMERIC(8,2),                  -- 薪资低端
    salary_max NUMERIC(8,2),                  -- 薪资高端
    -- 岗位结构
    top_job_titles JSONB,                     -- 热招岗位TOP10
    degree_requirement JSONB,                 -- 学历要求分布
    experience_requirement JSONB,             -- 经验要求分布
    industry_distribution JSONB,              -- 行业分布
    -- 元数据
    platform VARCHAR(50),                     -- BOSS直聘/智联/前程无忧
    data_source VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (major_id, city, platform, year, month)
);

-- 索引
CREATE INDEX idx_regional_job_city ON employment.regional_job_stats (city);
CREATE INDEX idx_regional_job_major ON employment.regional_job_stats (major_id);
CREATE INDEX idx_regional_job_search ON employment.regional_job_stats (city, major_id, year);
```

---

## 五、采集路线图（分月）

### 第 1-2 月：基础建设 + 核心数据

```
第1周：
  ├── 搭建 Python 环境 + 目录结构
  ├── 写 daily_run.py 骨架
  └── 跑通第一个爬虫 Demo（教育部院校名单）

第2周：
  ├── 院校数据全量采集
  ├── 专业目录采集
  ├── 阳光高考院校详情补充
  └── 每日论坛巡检上线（B站API优先）

第3周：
  ├── 每日论坛巡检扩展（知乎加入）
  ├── 招聘数据采集模块开发（最少1个招聘平台）
  └── 数据校验 + 入库管线

第4周：
  ├── 上海、浙江考试院数据采集（A组试点）
  ├── 省控线 + 一分一段 Demo
  └── 首份周报生成
```

### 第 3-4 月：省份扩展 + 招聘数据

```
第5-6周：
  ├── A组省份（山东、北京、江苏、天津、四川）
  ├── 招聘数据扩展到 10 个新一线城市
  └── 论坛巡检扩展到 Top 200 高校

第7-8周：
  ├── A组剩余省份完成
  ├── B组省份（陕西打头阵，本地重点）
  └── 招聘数据：建立专业→搜索关键词映射表

第9-12周：
  ├── B组省份逐个攻克
  ├── 排名数据采集（软科+校友会）
  ├── 就业质量报告PDF采集（Top 50高校）
  └── 首轮数据质量全面检查
```

### 第 5-8 月：录取季 + 深度数据

```
5月（政策窗口）：
  ├── 各省招生工作规定采集
  ├── 检查往年爬虫是否仍有效
  └── 排名数据更新

6月（出分窗口）：
  ├── 省控线实时采集（6/23-6/26）
  ├── 一分一段表实时采集
  └── 论坛巡检：高考志愿相关讨论热度最高峰，加大采集力度

7-8月（投档线窗口）：
  ├── A组省份投档线陆续发布
  ├── B组省份投档线发布
  ├── C组省份（西藏、青海、新疆等）人工辅助采集
  └── 招聘数据：关注"应届生招聘"旺季数据

9月：
  ├── 录取数据补漏（检查是否有省份遗漏）
  ├── 数据质量全面审计
  └── 开始就业质量报告采（Top 200 高校）
```

### 第 9-12 月：精细化 + 扩展

```
10-12月：
  ├── 就业质量报告批量采集（Top 200 高校）
  ├── UGC口碑深度分析：跨平台交叉比对
  ├── 地域招聘 × 专业关联分析报告
  ├── 城市产业集群与专业对应关系研究
  └── 年末数据总结 + 产品形态决策（小程序/网页/API）

面向次年：
  └── 整体巡检、框架升级、为新一年的录取季做准备
```

---

## 六、启动指令

以下命令启动每日采集（这是每天的入口）：

```bash
# 从 Hermes 中手动运行当日采集
cd D:/WorkBuddy/gaokao-database
python src/scripts/daily_run.py
```

每天执行后，查看当日简报：

```bash
cat reports/daily/$(date +%Y-%m-%d)_report.md
```

---

## 七、技术栈小结

| 层 | 技术 | 说明 |
|----|------|------|
| 爬虫框架 | Scrapy | 主力框架，结构化页面 |
| JS渲染 | Scrapy-Selenium / Playwright | 复杂交互、高频反爬站点 |
| 数据库 | PostgreSQL 16+ | 主力存储 |
| 缓存/去重 | Redis | 布隆去重、任务队列 |
| 校验 | 自定义 Python 模块 | data_validator.py |
| 情感分析 | SnowNLP / DeepSeek API | 论坛内容分析 |
| 招聘数据 | 招聘平台公开搜索接口 | 只统计数量，不抓详情 |
| 监控 | 自建日志 + 定时巡检 | 网站改版检测 |
| 自动化 | Hermes cron 定时任务 | 每天定时启动 |

---

## 八、变更日志（2026-07-04 代码审查修复）

### 安全性修复

| 问题 | 状态 | 说明 |
|------|------|------|
| DeepSeek API Key 硬编码 | ✅ 已修复 | 迁移到 `.env` 环境变量，不再硬编码在 app.py |
| DEEPSEEK_KEY.txt 冗余 | ✅ 已废弃 | 替换为指向 .env 的说明文件 |
| CORS 完全开放 | ✅ 已修复 | 从环境变量读取 `CORS_ORIGINS`，默认仅允许本机 |
| reload=True 生产风险 | ✅ 已修复 | 通过 `RELOAD` 环境变量控制，开发模式开启，生产关闭 |
| check_same_thread 安全 | ✅ 已修复 | 基于 contextvars 的协程安全连接管理 |

### 实用性问题修复

| 问题 | 状态 | 说明 |
|------|------|------|
| 中文编码乱码 | ✅ 已修复 | 统一使用 `utf-8` 编码，JSON 响应强制 `charset=utf-8` |
| import_to_sqlite.py 路径不一致 | ✅ 已修复 | 统一使用 `data/raw/` 路径 |
| 每次请求新建数据库连接 | ✅ 已优化 | contextvar 连接池：每个协程/请求复用同一连接 |
| 无请求日志 | ✅ 已添加 | 基于 logging 模块的请求日志 |
| 无健康检查端点 | ✅ 已添加 | `GET /api/health` 端点 |
| DeepSeek 无限流 | ✅ 已添加 | 令牌桶限流器 + 重试机制 |
| logger 未定义（daily_run.py） | ✅ 已修复 | 统一使用 logging.getLogger() |
| 无 .gitignore | ✅ 已添加 | 排除 .env、.db、__pycache__ 等 |
| 无依赖清单 | ✅ 已添加 | requirements.txt |
| 省控线仅 4 省 | ✅ 已扩展 | 覆盖全国 31 省市区（含港澳台以外的全部省份） |

### 新增功能

| 功能 | 说明 |
|------|------|
| `.env` 环境变量配置 | 所有可配置项集中管理，敏感信息不进代码 |
| `.env.example` | 配置模板，方便新环境部署 |
| 健康检查 | `GET /api/health` 检查数据库和 API 状态 |
| 隐私政策页 | `/static/privacy.html` |
| HTML 品牌 Footer | 驷马报考品牌 + 律所信息 + 免责声明 |
| 省控线迁移增强 | 支持按省份导入、JSON 导入导出、清空重建 |
