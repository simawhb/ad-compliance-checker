# 高考志愿填报数据库 — 数据采集项目策划书

> **版本：** v1.0  
> **日期：** 2026-06-29  
> **状态：** 策划阶段

---

## 目录

1. [项目概述](#1-项目概述)
2. [数据全景图](#2-数据全景图)
3. [数据源清单](#3-数据源清单)
4. [采集策略](#4-采集策略)
5. [存储方案](#5-存储方案)
6. [数据质量保障](#6-数据质量保障)
7. [落地路线图](#7-落地路线图)
8. [附录：工具链推荐](#8-附录工具链推荐)

---

## 1. 项目概述

### 1.1 目标

建立覆盖全国高校、专业、历年录取、招生政策、就业、排名及用户口碑的全维度高考志愿填报数据库，为后续开发志愿推荐、录取概率预测、专业分析等应用提供数据基础。

### 1.2 核心数据维度（7大板块）

| 板块 | 优先级 | 更新频率 | 数据量预估 |
|------|--------|----------|-----------|
| 院校数据 | P0 | 年度 | ~3000条 |
| 专业目录 | P0 | 年度 | ~1000条 |
| 历年录取 | P0 | 年度 | 千万级 |
| 招生政策 | P1 | 年度 | ~200份文件 |
| 就业数据 | P1 | 年度 | ~5000条 |
| 排名数据 | P2 | 年度/季度 | ~500条/排名 |
| 用户评价 | P2 | 持续 | 百万级 |

---

## 2. 数据全景图

### 2.1 院校数据（schools）

```sql
-- schools 表核心字段
school_id          -- 院校ID（主键，教育部院校代码）
name               -- 院校名称（全称，如"北京大学"）
name_aliases       -- 曾用名/别名（JSON数组，如["北京医科大学（合并前）"]）
name_en            -- 英文名称
code_edu           -- 教育部院校代码（5位数字，唯一）
code_gaokao        -- 高考院校代码（各省不同，JSON对象按省份存储）
code_yb            -- 研招网代码
level              -- 办学层次（本科/专科/职业本科）
type               -- 办学类型（综合/理工/农林/医药/师范/语言/财经/政法/体育/艺术/军事/民族）
category           -- 院校类别（普通院校/211/985/双一流/军校/中外合作/港澳）
is_211             -- 是否为211工程
is_985             -- 是否为985工程
is_double_first_class -- 是否为双一流
double_first_class_round -- 双一流批次（1/2）
admin_department   -- 主管部门（教育部/工信部/陕西省/…）
province           -- 所在省份
city               -- 所在城市
district           -- 所在区县
address            -- 详细地址
postal_code        -- 邮政编码
website            -- 官网URL
admission_office_phone -- 招生办电话
admission_office_website -- 招生网URL
email              -- 招生邮箱
logo_url           -- 校徽URL
thumbnail_url      -- 校门图片URL
established_year   -- 建校年份
history            -- 校史简介（文本）
area_acre          -- 占地面积（亩）
student_undergrad  -- 本科生人数
student_postgrad   -- 研究生人数
student_total      -- 在校生总数
faculty_count      -- 教职工总数
faculty_professor  -- 教授人数
library_volume     -- 图书馆藏书量（万册）
campus_count       -- 校区数量
campus_info        -- 校区信息（JSON，名称+地址+专业分布）
academician_count  -- 两院院士人数
doctoral_programs  -- 博士点数量
master_programs    -- 硕士点数量
key_labs           -- 国家重点实验室（JSON数组）
features           -- 办学特色标签（JSON数组）
scholarship_info   -- 奖助学金信息
tuition_range      -- 学费范围（JSON:{min,max,average}）
accommodation      -- 住宿条件描述
accommodation_fee  -- 住宿费范围
created_at         -- 记录创建时间
updated_at         -- 记录更新时间
data_source        -- 数据来源标记
data_version       -- 数据版本/年份
```

### 2.2 专业目录数据（majors + major_categories）

```sql
-- major_categories 学科门类表
category_id        -- 学科门类ID
category_name      -- 学科门类名称（如"工学"）
category_code      -- 学科门类代码（如"08"）
level              -- 层次（本科/专科）
parent_id          -- 上级类别ID（支持多级分类）

-- majors 专业表
major_id           -- 专业ID（主键，教育部专业代码）
name               -- 专业名称
name_full          -- 专业全称（含方向）
category_id        -- 所属学科门类ID
subject_group      -- 选科要求（3+1+2模式下的要求）
subject_group_3p3  -- 选科要求（3+3模式下的要求）
level              -- 学历层次（本科/专科）
study_years        -- 修业年限（4年/5年/3年）
degree             -- 授予学位（工学学士/理学学士/…）
description        -- 专业简介
main_courses       -- 主干课程（JSON数组）
typical_schools    -- 开设此专业的典型院校数
employment_rate    -- 全国平均就业率（最新）
employment_direction -- 就业方向描述
salary_avg         -- 全国平均薪资（元/月）
is_special         -- 是否国家特色专业
special_label      -- 特色标签（国家一流/省级一流/卓工/…）
version_year       -- 专业目录版本年份（如2024）
created_at
updated_at
```

### 2.3 历年录取数据（核心大表）

**设计方案：按年份分表，如 `admission_2024`、`admission_2023`… 每年一张表，联合查询通过视图/中间层合并。**

```sql
-- admission_{year} 录取数据表
id                 -- 自增ID
school_id          -- 院校ID
major_id           -- 专业ID（若为院校投档线则填NULL）
province           -- 省份
city_area          -- 所属地区（如西安市/咸阳市… 部分省份分地市招生）
batch              -- 批次名称（本科一批/本科二批/专科批/提前批/…）
batch_category     -- 批次类别（普通类/艺术类/体育类/强基计划/…）
student_category   -- 考生类别（文科/理科/综合/物理类/历史类/不分文理）
plan_count         -- 计划招生人数
admit_count        -- 实际录取人数
admit_score_min    -- 最低录取分数
admit_score_avg    -- 平均录取分数
admit_score_max    -- 最高录取分数
admit_score_diff   -- 线差（最低分 - 批次线）
admit_rank_min     -- 最低录取位次
admit_rank_avg     -- 平均录取位次
batch_score_line   -- 对应批次省控线
score_calculation  -- 总分计算方式（含听力/不含听力/750/…）
is_racial          -- 是否少数民族预科/定向等特殊类型
remark             -- 备注（如"含定向西藏就业"）
data_source        -- 数据来源（省考试院/阳光高考/…）
data_confidence    -- 数据可信度（high/medium/low）
created_at
updated_at

-- 索引建议：
-- composite index: (province, batch, student_category, school_id, major_id)
-- composite index: (school_id, year)
-- composite index: (major_id, year)
```

#### 省控线数据（province_score_lines）

```sql
-- province_score_lines 省控线表
id
province           -- 省份
year               -- 年份
batch              -- 批次（本科一批/本科二批/专科批/…）
student_category   -- 考生类别（文科/理科/物理类/历史类/…）
score_line         -- 批次分数线
created_at
updated_at
```

#### 一分一段表（score_rank_segments）

```sql
-- score_rank_segments 一分一段表
id
province           -- 省份
year               -- 年份
student_category   -- 考生类别
score              -- 分数
rank_start         -- 该分起始位次（累计人数上界）
rank_end           -- 该分结束位次（累计人数下界）
same_score_count   -- 同分人数
cumulative_count   -- 累计人数（>=该分）
data_source
created_at
```

### 2.4 招生政策数据（policies）

```sql
-- policies 招生政策表
id
province           -- 发布省份（"全国"表示教育部文件）
year               -- 适用年份
title              -- 文件标题
document_type      -- 文件类型（招生工作规定/志愿填报须知/投档规则/…）
url                -- 原文URL
content_text       -- 文本内容（markdown格式）
content_html       -- HTML原始内容
summary            -- AI自动摘要（200字以内）
key_points         -- 关键点提取（JSON数组）
batch_settings     -- 批次设置详情（JSON）
voting_rule        -- 投档规则（平行志愿/顺序志愿/…）
voting_ratio       -- 投档比例
admission_rule     -- 录取规则（分数优先/专业优先/专业级差/…）
admission_ratio    -- 提档比例
policy_changes     -- 与上年变化（JSON，字段级变化描述）
tags               -- 标签（"新高考改革"/"批次合并"/"专项计划"/…）
data_source
created_at
updated_at
```

### 2.5 就业数据（employment_stats + employment_reports）

```sql
-- employment_stats 就业统计数据
id
school_id          -- 院校ID（可为NULL）
major_id           -- 专业ID（可为NULL，至少一个不为NULL）
year               -- 统计年份
province           -- 所在省份（可为NULL表示全国）
employment_rate    -- 就业率（百分比）
employment_rate_profession -- 专业对口率
salary_avg         -- 平均月薪
salary_median      -- 月薪中位数
salary_top_25      -- 前25%月薪
salary_bottom_25   -- 后25%月薪
industry_top3      -- 主要就业行业TOP3（JSON数组）
employer_top5      -- 主要就业单位TOP5（JSON数组）
city_distribution  -- 就业城市分布（JSON，如{"北京":30%, "上海":20%}）
further_study_rate -- 升学率（读研/读博）
overseas_rate      -- 出国率
data_source        -- 来源学校/教育部/第三方
created_at
updated_at

-- employment_reports 详细就业质量报告
id
school_id
year
title
url                 -- 报告原文URL（学校就业网）
file_url            -- PDF附件URL
summary             -- AI摘要
key_metrics         -- 关键指标（JSON）
has_attachment      -- 是否有PDF附件
created_at
```

### 2.6 排名数据（rankings）

```sql
-- rankings 排名表
id
ranking_name       -- 排名名称（软科/校友会/QS/US News/泰晤士/ESI/教育部学科评估）
ranking_type       -- 排名类型（综合排名/学科排名/专业排名）
ranking_year       -- 排名年份
school_id          -- 院校ID
major_id           -- 专业/学科ID（学科排名时用，综合排名时为NULL）
rank               -- 具体排名
rank_total         -- 参评总数
score              -- 总分/评分
rank_change        -- 较上年变化（+5/-3/NEW/-）
tier               -- 档次（学科评估用：A+/A/A-/B+/…）
level_tag          -- 等级标签（"世界一流"/"中国顶尖"/"区域一流"/…）
data_source        -- 来源URL/出版物
created_at
updated_at
```

### 2.7 用户评价 / 口碑数据（user_reviews + forum_posts）

```sql
-- user_reviews 用户评价（短评类）
id
school_id
major_id           -- 可为NULL（学校整体评价）
platform           -- 平台来源（知乎/小红书/贴吧/豆瓣/抖音/B站/掌上高考/…）
platform_url       -- 原文链接
author_id          -- 作者标识（脱敏，MD5）
author_type        -- 作者身份（在校生/毕业生/家长/教师/其他）
content_text       -- 评价内容
content_length     -- 内容长度
sentiment          -- 情感倾向（positive/negative/neutral）
sentiment_score    -- 情感得分（-1.0 ~ 1.0）
tags               -- 标签（"宿舍差"/"就业好"/"学习氛围"/…）
like_count         -- 点赞数
reply_count        -- 回复数
publish_time       -- 发布时间
crawl_time         -- 采集时间
is_useful          -- 是否对志愿填报有参考价值（AI判断）
data_source
created_at

-- forum_posts 长帖/文章
id
platform
thread_id          -- 帖子ID
title              -- 帖子标题
content_text       -- 正文内容
school_id          -- 关联院校
major_id           -- 关联专业
platform_url
author_id
view_count         -- 阅读量
like_count
reply_count
favorite_count     -- 收藏数
publish_time
crawl_time
quality_score      -- 内容质量分（1-10，AI评估）
summary            -- AI摘要
data_source
created_at
```

### 2.8 元数据管理

```sql
-- crawl_tasks 采集任务跟踪表
id
task_name          -- 任务名称
target_url         -- 目标URL/网站
data_type          -- 数据类型（school/admission/policy/…）
crawl_strategy     -- 采集策略（api/scrapy/selenium/…）
frequency          -- 执行频率（once/daily/weekly/yearly）
last_run_at        -- 上次执行时间
last_status        -- 上次状态（success/failed/partial）
error_log          -- 错误日志
next_run_at        -- 下次执行时间
enabled            -- 是否启用
created_at
updated_at

-- data_change_log 数据变更日志
id
table_name         -- 变更表名
row_id             -- 变更行ID
change_type        -- 变更类型（insert/update/delete）
old_values         -- 旧值（JSON）
new_values         -- 新值（JSON）
changed_by         -- 变更人（system/manual）
change_reason      -- 变更原因
created_at
```

---

## 3. 数据源清单

### 3.1 教育部官方平台

| 数据源 | URL | 数据类别 | 采集方式 | 频率 | 反爬难度 |
|--------|-----|---------|---------|------|---------|
| 阳光高考（院校库） | `https://gaokao.chsi.com.cn/sch/` | 院校基本信息、招生章程 | Scrapy + 解析HTML | 年度 | ⭐⭐ |
| 阳光高考（专业库） | `https://gaokao.chsi.com.cn/zyk/` | 专业目录、专业介绍 | Scrapy + JSON接口 | 年度 | ⭐ |
| 阳光高考（录取数据） | `https://gaokao.chsi.com.cn/lq/` | 历年录取分数（部分省份） | Selenium + 解析 | 年度 | ⭐⭐⭐ |
| 学信网 | `https://www.chsi.com.cn/` | 学籍学历验证信息 | —（只做参考） | — | ⭐⭐⭐⭐ |
| 教育部全国高等学校名单 | `http://www.moe.gov.cn/jyb_xxgk/s5743/s5744/202406/t20240620_1135877.html` | 全国高校名单（官方权威清单） | 直接下载PDF/Excel | 年度 | ⭐ |
| 教育部专业目录 | `http://www.moe.gov.cn/s78/A08/gjs_left/moe_1034/` | 本科/专科专业目录 | 直接下载PDF | 年度 | ⭐ |
| 教育部学科评估结果 | `http://www.moe.gov.cn/jyb_xwfb/xw_fbh/moe_2069/` | 学科评估（第四轮/第五轮） | 解析HTML | 多年一次 | ⭐ |
| 研招网 | `https://yz.chsi.com.cn/` | 硕士博士专业信息 | —（后备参考） | — | ⭐⭐ |

### 3.2 各省教育考试院（核心录取数据源）

**以下为主要省份考试院官网及数据特点：**

| 省份 | 考试院官网 | 数据特点 | 采集难度 | 推荐工具 |
|------|-----------|---------|---------|---------|
| 北京 | `https://www.bjeea.cn/` | 一分一段表公开完整；各校录取分按年发布 | ⭐⭐ | Scrapy |
| 天津 | `http://www.zhaokao.net/` | 数据格式较规范 | ⭐⭐ | Scrapy |
| 河北 | `http://www.hebeea.edu.cn/` | 数据量大人多，数据动态更新 | ⭐⭐⭐ | Selenium |
| 山西 | `http://www.sxkszx.cn/` | 信息公开较慢 | ⭐⭐ | Scrapy |
| 内蒙古 | `https://www.nm.zsks.cn/` | 数据较全 | ⭐⭐ | Scrapy |
| 辽宁 | `https://www.lnzsks.com/` | 投档线公开较全 | ⭐⭐ | Scrapy |
| 吉林 | `http://www.jleea.com.cn/` | 数据格式不规范 | ⭐⭐⭐ | 人工辅助 |
| 黑龙江 | `https://www.lzk.hl.cn/` | 数据较为完整 | ⭐⭐ | Scrapy |
| 上海 | `https://www.shmeea.edu.cn/` | 数据公开好，但结构独特（3+3） | ⭐⭐ | Scrapy |
| 江苏 | `https://www.jseea.cn/` | 数据公开较好 | ⭐⭐ | Scrapy |
| 浙江 | `https://www.zjzs.net/` | 数据公开优秀，最全之一 | ⭐ | API/Scrapy |
| 安徽 | `https://www.ahzsks.cn/` | 数据公开一般 | ⭐⭐⭐ | Selenium |
| 福建 | `https://www.eeafj.cn/` | 数据公开较好 | ⭐⭐ | Scrapy |
| 江西 | `http://www.jxeea.cn/` | 数据公开一般 | ⭐⭐⭐ | Selenium |
| 山东 | `https://www.sdzk.cn/` | 数据公开好，新高考先行者 | ⭐⭐ | Scrapy |
| 河南 | `http://www.haeea.cn/` | 高考大省，数据量大但公开一般 | ⭐⭐⭐ | Selenium |
| 湖北 | `http://www.hbea.edu.cn/` | 数据公开较好 | ⭐⭐ | Scrapy |
| 湖南 | `https://www.hneeb.cn/` | 数据公开一般 | ⭐⭐⭐ | Selenium |
| 广东 | `https://eea.gd.gov.cn/` | 数据公开较好 | ⭐⭐ | Scrapy |
| 广西 | `https://www.gxeea.cn/` | 数据公开一般 | ⭐⭐⭐ | Selenium |
| 海南 | `http://ea.hainan.gov.cn/` | 数据公开一般 | ⭐⭐ | Scrapy |
| 重庆 | `https://www.cqksy.cn/` | 数据公开较好 | ⭐⭐ | Scrapy |
| 四川 | `https://www.sceea.cn/` | 数据公开较好 | ⭐⭐ | Scrapy |
| 贵州 | `http://zsksy.guizhou.gov.cn/` | 数据公开一般 | ⭐⭐⭐ | Selenium |
| 云南 | `https://www.ynzs.cn/` | 数据公开一般 | ⭐⭐⭐ | Selenium |
| 西藏 | `http://zsks.edu.xizang.gov.cn/` | 数据稀少 | ⭐⭐⭐⭐ | 人工辅助 |
| 陕西 | `https://www.sneea.cn/` | **重点关注**（本地市场）| ⭐⭐ | Scrapy |
| 甘肃 | `https://www.ganseea.cn/` | 数据公开一般 | ⭐⭐ | Scrapy |
| 青海 | `http://www.qhjyks.com/` | 数据稀少 | ⭐⭐⭐ | 人工辅助 |
| 宁夏 | `https://www.nxjyks.cn/` | 数据公开一般 | ⭐⭐ | Scrapy |
| 新疆 | `http://www.xjzk.gov.cn/` | 数据稀少 | ⭐⭐⭐ | 人工辅助 |

**采集策略：** 按省份分爬虫模块，优先覆盖前20大生源省份（河南/广东/山东/四川/江苏/河北/湖南/安徽/湖北/浙江等）。

### 3.3 排名数据源

| 排名名称 | 官网/数据地址 | 采集方式 | 说明 |
|---------|-------------|---------|------|
| 软科中国大学排名 | `http://www.shanghairanking.cn/rankings/bcur/2025` | Scrapy + HTML | 最全的国内排名，含总榜+分类+专业排名 |
| 软科世界大学学术排名(ARWU) | `http://www.shanghairanking.cn/rankings/arwu/2025` | Scrapy + HTML | 国际排名 |
| 校友会排名 | `https://www.cuaa.net/` | Scrapy + HTML | 国内排名，含星级评价 |
| QS世界大学排名 | `https://www.qschina.cn/university-rankings/world-university-rankings/` | Scrapy + HTML | 国际排名 |
| US News 排名 | `https://www.usnews.com/best-colleges` | Selenium | 有反爬，需代理 |
| THE泰晤士排名 | `https://www.timeshighereducation.com/world-university-rankings/` | Selenium | 有反爬 |
| 教育部学科评估 | 教育部官网 PDF | PDF解析（pdfplumber/camelot） | 第四轮已公开，第五轮部分公开 |
| ESI学科排名 | `https://esi.clarivate.com/` | — | 需授权，不优先 |

### 3.4 就业数据源

| 数据源 | 地址 | 说明 | 采集方式 |
|-------|------|------|---------|
| 各高校就业质量报告 | 各校就业网（如`https://career.pku.edu.cn/`） | 每年发布PDF | Scrapy批量下载PDF → LLM提取结构化数据 |
| 教育部就业统计 | 教育部年度就业白皮书 | 宏观数据 | PDF解析 |
| 学信网就业平台 | `https://www.chsi.com.cn/` | — | 受限 |
| 第三方数据（麦可思） | `https://www.mycos.com.cn/` | 专业就业率数据 | 有收费墙，可购买报告 |
| BOSS直聘研究院 | `https://www.zhipin.com/` | 薪资大数据 | 公开年度报告，PDF采集 |
| 智联招聘 | `https://www.zhaopin.com/` | 行业薪资数据 | 公开报告 |
| 高考志愿APP | 如掌上高考、高考帮等 | — | 抓取APP接口 |

### 3.5 社交媒体 / UGC数据源

| 平台 | 数据类型 | 采集方式 | 法律风险 | 策略建议 |
|------|---------|---------|---------|---------|
| **知乎** | 院校评价、专业话题、"在XX大学就读是什么体验"等问答 | Scrapy爬虫 / 知乎API（有限） | ⚠️ 公开页面合规 | 优先采集：高赞回答(>100赞)、热门话题 |
| **小红书** | 志愿填报笔记、宿舍实拍、避坑帖 | Selenium / App抓包 | ⚠️ 反爬严格 | 按关键词搜索，只采公开笔记 |
| **百度贴吧** | 各大学吧讨论 | Scrapy | ✅ 低风险 | 按学校名搜索吧，采精华帖 |
| **豆瓣** | 院校小组讨论 | Scrapy | ✅ 低风险 | 按学校/专业小组采集 |
| **抖音/快手** | 短视频评论、博主推荐 | 无公开API | ⚠️ 受限 | 只作为线索参考，不主动爬 |
| **B站** | 志愿填报视频弹幕/评论 | B站API（开放） | ✅ 低风险 | `api.bilibili.com` 开放接口 |
| **掌上高考** | 用户评价/评分 | Selenium / App逆向 | ⚠️ 反爬 | 重点采集评价分数 |
| **高考帮APP** | 院校评分、专业推荐 | App抓包 | ⚠️ 反爬严格 | 酌情 |

### 3.6 商业数据 / API服务

| 服务商 | 说明 | 费用 | 建议 |
|-------|------|------|------|
| 百度智能云高考服务 | `https://ai.baidu.com/` 教育API | 收费 | 可作为辅助验证 |
| 阿里云-高考数据API | 院校/专业/录取数据 | 收费 | 可作为初期数据快速获取渠道 |
| 聚合数据 | `https://www.juhe.cn/` 高考API | 免费/收费 | 可尝试免费额度 |
| 天行数据 | `https://www.tianapi.com/` 高考接口 | 免费/收费 | 可尝试 |
| 各志愿填报APP（优志愿/高考帮/掌上高考/完美志愿） | 可直接购买数据 | 按年收费 | 最省事但不推荐长期依赖 |

---

## 4. 采集策略

### 4.1 技术栈选择

```
采集层:
├── Scrapy (主力框架)          → 结构化页面采集
├── Scrapy-Selenium (中间件)   → JS渲染页面
├── Playwright (备用)          → 复杂交互页面
├── Scrapy-Playwright (中间件) → Playwright集成
├── ScrapyRT / scrapyrt        → 爬虫API化

解析层:
├── Parsel / lxml / BeautifulSoup4  → HTML解析
├── pdfplumber / camelot            → PDF表格提取
├── python-docx                     → Word文档
├── pypdf / PyMuPDF                 → PDF文本提取
├── jieba / hanlp                   → 中文分词（内容分析）

存储层:
├── SQLite (开发/单机)        → 开发调试
├── PostgreSQL (生产)         → 结构化数据主力库
├── MongoDB (选配)            → 非结构化/半结构化数据
├── Redis                     → 任务队列/去重缓存

监控层:
├── Scrapy Log / Stats         → 爬虫状态监控
├── Sentry / 自建日志          → 错误告警
├── Prometheus + Grafana       → 指标可视化（后期）
```

### 4.2 结构化数据采集方案

#### 4.2.1 教育部院校名单 + 专业目录
```
采集方式：直接下载官方发布文件
工具：requests + python-docx/pdfplumber
频率：每年教育部更新后执行一次
流程：
  1. 监控教育部官网公告（RSS/定期检查URL变更）
  2. 检测到新名单发布 → 下载文件
  3. 解析PDF/Word → 清洗 → 入库
  4. 对比上一版本，标记增删改
```

#### 4.2.2 各省考试院录取数据
```
省份爬虫通用框架（如 gd_province_spider.py）：

class ProvinceSpider(scrapy.Spider):
    name = "gdedu"
    allowed_domains = ["eea.gd.gov.cn"]
    start_urls = ["https://eea.gd.gov.cn/..."]
    
    custom_settings = {
        "DOWNLOAD_DELAY": 2,          # 礼貌延迟2秒
        "CONCURRENT_REQUESTS": 4,     # 并发4线程
        "ROTATING_PROXY_LIST": "proxies.txt",
        "USER_AGENT_LIST": "user_agents.txt",
        "RETRY_TIMES": 3,
        "COOKIES_ENABLED": False,
    }
    
    核心爬取逻辑：
    1. 按年份遍历 → 找到投档线公告页面
    2. 解析表格HTML → 提取（院校+专业+计划数+投档分+位次）
    3. 数据校验（分数字段非空/位次非零/批次归类）
    4. 输出JSON Lines → 批量入库

省份特殊处理：
  - 浙江：数据最全，可直接从 zjzs.net 获取完整CSV
  - 山东：数据在 sdzk.cn 分批次发布，需多页追踪
  - 河南：haeea.cn 表格结构较乱，需正则+人工标注
  - 陕西：sneea.cn 数据以PDF发布，需pdfplumber提取
```

#### 4.2.3 一分一段表采集
```
特殊处理方案：
1. 每年6月23日-26日各省公布成绩时集中采集
2. 优先从考试院获取官方PDF/Excel
3. 部分省份以图片发布 → LLM OCR（用mcp-vision处理）
4. 数据校验：最后一档累计人数应等于该省当年考生总数
5. 存入 score_rank_segments 表，与 admission 表关联使用
```

### 4.3 UGC / 论坛内容采集方案

#### 4.3.1 知乎采集
```
技术方案：
  - 知乎非登录可浏览页面内容
  - 使用 Scrapy 直接爬取公开页面
  - 搜索结果URL: https://www.zhihu.com/search?type=content&q=关键词

采集关键词策略（组合方式）：
  基础词集: ["高考志愿", "大学", "专业", "录取"]
  院校词集: ["北京大学", "清华大学", ...]  // 从schools表读取
  专业词集: ["计算机专业", "法学专业", ...]  // 从majors表读取
  场景词集: ["在读体验", "值得去吗", "避雷", "就业", "宿舍环境"]

反爬对策：
  - 请求频率：每5-10秒一个请求
  - Cookie管理：定期更换，可模拟浏览器登录状态
  - IP代理：使用收费代理池（如 快代理/芝麻代理）
  - User-Agent轮换：不少于20个主流UA

内容处理管线：
  原始HTML → lxml提取（标题/内容/赞同数/评论数） 
           → 清洗HTML标签 → Markdown转换 
           → 作者脱敏（MD5） → NLP情感分析 
           → 内容质量评分 → 入forum_posts表
```

#### 4.3.2 小红书采集
```
技术方案：
  - 小红书反爬极严，需谨慎
  - 使用 Playwright 模拟真实浏览器操作
  - 关键词搜索 → 笔记列表 → 笔记详情

关键注意：
  1. 频率控制在每分钟<=5次
  2. 使用真实浏览器指纹（Playwright stealth）
  3. 必须使用高质量代理IP（移动/联通4G代理最优）
  4. 采集内容：仅公开可见的笔记标题和正文
  5. 避免采集用户个人信息（昵称除外）
  6. 遵守 robots.txt，控制采集总量

法律红线：
  - 不采集私信内容
  - 不采集非公开账号内容
  - 采集内容不做二次售卖
  - 存储时做数据脱敏（用户ID哈希化）
```

#### 4.3.3 B站 采集
```
B站有官方API可直接使用，是UGC数据中门槛最低的：
  - 搜索API: https://api.bilibili.com/x/web-interface/search/all/v2
  - 视频评论: https://api.bilibili.com/x/v2/medialist/resource/list
  - 无需登录即可调用（有频率限制）
```

### 4.4 反爬虫综合对策

| 技术手段 | 适用场景 | 实现方式 | 成本 |
|---------|---------|---------|------|
| **延迟策略** | 所有爬虫 | `DOWNLOAD_DELAY` 随机延迟 2-5秒 | 免费 |
| **User-Agent轮换** | 所有爬虫 | Scrapy-UAMiddleware / 自建UA池 | 免费 |
| **代理IP（动态）** | 考试院/知乎/小红书 | 付费代理池（快代理/芝麻/站大爷） | ¥100-500/月 |
| **代理IP（静态）** | 教育部/普通站点 | 3-5个住宅IP轮换 | ¥50-100/月 |
| **浏览器指纹** | 小红书/抖音 | playwright-stealth | 免费 |
| **Cookie管理** | 需要登录态 | scrapy-cookies / 浏览器cookie导出 | 免费 |
| **验证码破解** | 少数极端情况 | OCR（PaddleOCR）或打码平台 | ¥0.01-0.05/次 |
| **请求间隔随机化** | 所有 | 高斯分布随机间隔 | 免费 |
| **页面缓存** | 所有（防重复） | Scrapy HTTPCache + Redis去重 | 免费 |

### 4.5 PDF文件批量处理（就业报告/政策文件）

```
管线设计：

1. 批量下载PDF
   ↓
2. 分类器（规则+ML判断文件类型）
   ├── 表格型PDF（录取数据/统计报表）
   │   └── camelot-py (Lattice模式) → pandas DataFrame → 入库
   ├── 文本型PDF（政策文件/说明文档）
   │   └── pdfplumber.extract_text() → LLM结构化提取 → 入库
   └── 扫描型PDF（图片文件）
       └── PaddleOCR → 文本 → LLM结构化提取 → 入库
   ↓
3. 质量检查 → 人工标注困难案例 → 入库
```

---

## 5. 存储方案

### 5.1 数据库选型

| 数据库 | 用途 | 理由 |
|-------|------|------|
| **PostgreSQL 16+** | 主力存储 | 支持JSONB（灵活性）、时间分区（按年）、全文检索（搜索）、PostGIS（地图功能预留） |
| **Redis** | 缓存/去重/任务队列 | 布隆过滤器去重、爬虫URL队列缓存 |
| **SQLite** | 开发调试/离线场景 | 零配置，便于本地开发 |

**不建议：**
- MySQL：PG在JSONB、分区表、全文检索方面优于MySQL
- MongoDB：结构化数据为主，Mongo无明显优势
- Elasticsearch：初期不需要，后期搜索量大可加入

### 5.2 PostgreSQL 核心设计

#### 5.2.1 数据库与模式

```sql
-- 创建数据库
CREATE DATABASE gaokao_db WITH ENCODING 'UTF8' LC_COLLATE 'zh_CN.UTF-8';

-- schema设计
CREATE SCHEMA base;       -- 基础数据（院校、专业）
CREATE SCHEMA admission;  -- 录取数据
CREATE SCHEMA policy;     -- 政策数据
CREATE SCHEMA employment; -- 就业数据
CREATE SCHEMA ranking;    -- 排名数据
CREATE SCHEMA user_content; -- 用户评价
CREATE SCHEMA meta;        -- 元数据（采集任务、变更日志）
```

#### 5.2.2 表分区策略（录取数据）

```sql
-- 录取数据使用按年分区表
CREATE TABLE admission.admission_data (
    id BIGSERIAL,
    year INTEGER NOT NULL,
    school_id VARCHAR(10) NOT NULL,
    major_id VARCHAR(20),
    province VARCHAR(20) NOT NULL,
    batch VARCHAR(50),
    student_category VARCHAR(20),
    plan_count INTEGER,
    admit_count INTEGER,
    admit_score_min NUMERIC(5,1),
    admit_score_avg NUMERIC(5,1),
    admit_score_max NUMERIC(5,1),
    admit_rank_min INTEGER,
    admit_rank_avg INTEGER,
    score_line NUMERIC(5,1),
    data_source VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (id, year)
) PARTITION BY RANGE (year);

-- 创建各年分区
CREATE TABLE admission.admission_2024 PARTITION OF admission.admission_data
    FOR VALUES FROM (2024) TO (2025);
CREATE TABLE admission.admission_2023 PARTITION OF admission.admission_data
    FOR VALUES FROM (2023) TO (2024);
-- ... 以此类推，每年自动创建新分区
```

#### 5.2.3 索引策略

```sql
-- 录取数据表索引（核心查询场景）
CREATE INDEX idx_admission_school_year ON admission.admission_data (school_id, year);
CREATE INDEX idx_admission_province_batch ON admission.admission_data (province, batch, student_category);
CREATE INDEX idx_admission_major_year ON admission.admission_data (major_id, year);
CREATE INDEX idx_admission_score_rank ON admission.admission_data (year, province, student_category, admit_score_min);
-- 联合索引：按省份、年份、位次查询——最常用场景
CREATE INDEX idx_admission_search ON admission.admission_data 
    (province, year, student_category, batch, admit_rank_min);

-- 院校表索引
CREATE INDEX idx_school_province ON base.schools (province);
CREATE INDEX idx_school_level ON base.schools (level);
CREATE INDEX idx_school_category ON base.schools (category);
CREATE INDEX idx_school_name_trgm ON base.schools USING gin (name gin_trgm_ops);  -- 模糊搜索

-- 专业搜索索引
CREATE INDEX idx_major_name_trgm ON base.majors USING gin (name gin_trgm_ops);

-- 排名表索引
CREATE INDEX idx_rankings_school ON ranking.rankings (school_id, ranking_year);
CREATE INDEX idx_rankings_name ON ranking.rankings (ranking_name);
```

#### 5.2.4 PostgreSQL 扩展需求

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- 模糊搜索
CREATE EXTENSION IF NOT EXISTS pg_stat_statements; -- 查询性能分析
CREATE EXTENSION IF NOT EXISTS pg_cron;   -- 定时任务（可选）
```

### 5.3 数据版本管理

#### 5.3.1 年份维度策略
```
方案：按年份分表/分区 + 数据行标记版本年

院校数据：
  - 院校基本信息变化不大，单一表 + updated_at 追踪
  - 大变更（改名/合并/升格）记录到 name_aliases 和历史表

专业数据：
  - 每年教育部发布新专业目录时建立新版本记录
  - 用 version_year 字段区分
  - 专业代码不变，名称可能微调

录取数据：
  - 核心使用按年分区
  - 不支持跨年修改历史数据
  - 若某省修正了已发布数据，通过 data_change_log 记录修订

排名数据：
  - 每年/每期排名都是独立记录
  - 不覆盖上年排名，按年份存储便于趋势分析
```

#### 5.3.2 快照表设计（选配）

```sql
-- 如果需要保存某时间点的完整数据快照（如2024年8月1日时的数据状态）
CREATE TABLE meta.data_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    snapshot_name VARCHAR(100),
    snapshot_time TIMESTAMP DEFAULT NOW(),
    included_tables TEXT[],  -- 包含哪些表
    row_counts JSONB,        -- 各表行数
    file_path VARCHAR(500),  -- 备份文件路径
    note TEXT
);
```

### 5.4 文件存储

```sql
-- 附件/文件存储（PDF报告、院校图片等）
CREATE TABLE meta.file_attachments (
    id SERIAL PRIMARY KEY,
    file_type VARCHAR(50),        -- pdf_report / school_logo / campus_photo / policy_attachment
    source_table VARCHAR(100),     -- 关联表名
    source_row_id VARCHAR(50),     -- 关联行ID
    original_filename VARCHAR(500),
    stored_filename VARCHAR(500),
    file_size_bytes BIGINT,
    file_hash VARCHAR(64),         -- SHA256用于去重
    storage_path VARCHAR(1000),    -- 本地文件路径或对象存储路径
    url VARCHAR(1000),
    mime_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**文件物理存储建议：**
```
D:\WorkBuddy\gaokao-database\data\
├── attachments\
│   ├── school_logos\        # 校徽
│   ├── campus_photos\       # 校园图片
│   ├── employment_reports\  # 就业质量报告PDF
│   ├── policy_files\        # 政策文件PDF
│   └── ranking_reports\     # 排名报告
├── exports\                 # 数据导出
├── backups\                 # 数据库备份
└── raw\                     # 爬虫原始数据暂存
```

---

## 6. 数据质量保障

### 6.1 去重策略

| 数据表 | 去重键 | 策略 |
|-------|--------|------|
| schools | `code_edu`（教育部代码） | 新数据覆盖旧数据，保留变更历史 |
| majors | `major_id` + `version_year` | 同代码同版本号不重复 |
| admission_data | `school_id+major_id+province+year+batch+student_category` | 同记录覆盖（以考试院数据为准） |
| province_score_lines | `province+year+batch+student_category` | 唯一约束，UPSERT |
| score_rank_segments | `province+year+student_category+score` | 唯一约束 |
| rankings | `ranking_name+ranking_year+school_id+major_id` | 唯一约束 |
| user_reviews | `platform+platform_url` | URL去重 |

**去重实现：**
```sql
-- UPSERT 示例：录取数据
INSERT INTO admission.admission_2024 (...)
VALUES (...)
ON CONFLICT (school_id, major_id, province, batch, student_category)
DO UPDATE SET
    admit_score_min = EXCLUDED.admit_score_min,
    admit_rank_min = EXCLUDED.admit_rank_min,
    updated_at = NOW();
```

**爬虫层去重：**
```
Scrapy 本身用 RFPDupeFilter（基于请求指纹）
额外增加 Redis 布隆过滤器：
  - key: "gaokao:url_seen:{spider_name}"
  - 百万级URL，内存仅10MB左右
```

### 6.2 数据一致性校验规则

```python
# 校验脚本示例（Python/PostgreSQL）

VALIDATION_RULES = {
    "admission_data": [
        ("admit_score_min > 0", "最低分不能为0或负数"),
        ("admit_rank_min > 0", "位次不能为0"),
        ("admit_score_min <= admit_score_max", "最低分不能高于最高分"),
        ("plan_count >= 0", "计划数不能为负数"),
        ("admit_rank_min < 500000", "理科位次不超过50万（省校验）"),
    ],
    "schools": [
        ("code_edu ~ '^\d{5}$'", "教育部代码必须是5位数字"),
        ("province IS NOT NULL", "省份不能为空"),
        ("name IS NOT NULL", "院校名称不能为空"),
    ],
    "province_score_lines": [
        ("score_line > 0", "批次线必须为正数"),
    ],
    "score_rank_segments": [
        ("cumulative_count > 0", "累计人数必须为正"),
        ("rank_end >= rank_start", "结束位次 >= 起始位次"),
    ],
}

# 运行方式：每日/每周自动执行一次校验，不合格数据标记 + 告警
```

### 6.3 缺失值处理策略

| 字段类型 | 缺失处理方式 |
|---------|-------------|
| 录取最低分 | 标记为 NULL，不补值；UI显示"暂无数据" |
| 录取位次 | 标记为 NULL；部分省份不公布位次 |
| 平均分/最高分 | 优先从原始数据获取，否则NULL |
| 就业率 | 标记NULL，来源可靠度低的标记置信度 |
| 学费 | 从学校官网招生章程获取，获取失败则NULL |
| 院校简介/专业描述 | 用LLM根据已知信息生成，标注"AI生成" |
| 选科要求 | 查询该省教育考试院要求，无法获取则标注"待确认" |

### 6.4 数据更新机制

```
分层更新策略：

P0（关键数据）- 年度更新：
  1. 每年5-6月：更新院校名单、专业目录（教育部发布）
  2. 每年6-8月：更新录取数据（各省陆续发布）
  3. 触发方式：手动启动 + 定时检查

P1（重要数据）- 年度/季度更新：
  1. 每年10-12月：更新就业质量报告
  2. 每年政策发布期：更新招生政策
  3. 排名发布时：更新软科/校友会排名

P2（辅助数据）- 持续更新：
  1. 用户评价：视资源情况批量采集
  2. 论坛内容：定期（月/季）增量采集

更新流程：
  ① 检测到新数据发布 → ② 启动对应爬虫任务 
  → ③ 暂存到 staging 表 → ④ 运行数据校验
  → ⑤ 校验通过 → 写入主表 → ⑥ 标记数据版本
  → ⑦ 记录变更日志 → ⑧ 更新成功
  → ⑤ 校验失败 → 告警 → 人工介入
```

---

## 7. 落地路线图

### Phase 1: MVP（2-3个月）— 可实际使用的数据库

**目标：** 覆盖全国90%以上高校的核心录取数据（近3年），加上基础院校和专业信息，让一个简单的志愿推荐查询功能跑起来。

| 任务 | 时间 | 产出 |
|------|------|------|
| 1.1 数据库搭建 | 第1周 | PostgreSQL建库、建表、分区配置 |
| 1.2 院校数据采集 | 第1-2周 | 教育部名单+阳光高考院校库 → 3000+高校 |
| 1.3 专业目录采集 | 第2周 | 教育部本科/专科专业目录 → 全量专业 |
| 1.4 近3年录取数据 | 第3-8周 | Top15省份×近3年×本科批 → 预计200万+条 |
| 1.5 省控线+一分一段 | 第3-8周 | Top15省份近3年数据 |
| 1.6 批量导入脚本 | 第3-4周 | 数据导入管线（CSV/JSON → DB） |
| 1.7 数据校验 | 全周期 | 自动校验规则 + 手动抽查 |
| 1.8 基础API封装 | 第9-10周 | RESTful API（供前端/小程序调用） |

**Phase 1 数据覆盖范围：**
- 院校：全国所有高校
- 专业：教育部全量专业目录
- 录取：Top15省份，2022-2024年，本科一批/二批/专科批
- 省控线：Top15省份
- 一分一段：Top15省份

**Top15省份优先级排序：**
1. 广东、河南、山东、四川、江苏
2. 河北、湖南、安徽、湖北、浙江
3. 陕西、福建、江西、广西、云南

### Phase 2: 扩展期（4-6个月）— 全面覆盖

**目标：** 覆盖全国31省全部录取数据（至少5-10年），加入就业数据和排名，增加更多省份和年份。

| 任务 | 时间 | 产出 |
|------|------|------|
| 2.1 剩余省份覆盖 | 第11-14周 | 所有省份录取数据、省控线、一分一段 |
| 2.2 历史数据回溯 | 第11-16周 | 扩展到2018年-当前（7年+） |
| 2.3 就业数据采集 | 第15-20周 | 就业质量报告→结构化数据 |
| 2.4 排名数据采集 | 第15-17周 | 软科/校友会/学科评估 |
| 2.5 招生政策采集 | 第17-19周 | 各省2024/2025招生工作规定 |
| 2.6 数据质量增强 | 第18-20周 | 交叉验证、异常检测完善 |
| 2.7 院校详细信息 | 第19-22周 | 学费、宿舍、校区、学科点 |
| 2.8 用户评价初步采集 | 第20-24周 | 知乎+B站+掌上高考数据 |

### Phase 3: 精细化运营（持续）

**目标：** 数据精细化、多维度、实时化，建立数据竞争壁垒。

| 任务 | 说明 |
|------|------|
| 3.1 UGC深度采集 | 小红书/贴吧/抖音等多平台，情感分析+标签化 |
| 3.2 录取预测模型 | 基于历史数据+当年位次，预测录取概率 |
| 3.3 实时数据跟踪 | 录取期间实时更新，数据刷新≤24h |
| 3.4 选科数据分析 | 新高考选科大数据，组合分析 |
| 3.5 专业趋势分析 | 就业率变化趋势、薪资增长曲线 |
| 3.6 院校对比系统 | 多维度对比（就业/排名/分数/口碑） |
| 3.7 数据开放平台 | 数据API服务、数据报表导出 |
| 3.8 生态建设 | 数据贡献者社区（院校百科编辑等） |

---

## 8. 附录：工具链推荐

### 8.1 核心爬虫框架

```yaml
爬虫框架选型:
  Scrapy: 
    适用: 结构化页面（院校/专业/排名/考试院表格）
    版本: >=2.12
    关键插件:
      - scrapy-playwright: JS渲染
      - scrapy-rotating-proxies: 代理轮换
      - scrapy-user-agents: UA轮换
      - scrapy-splash: 轻量JS渲染（备选）
    项目结构建议:
      project/gk_crawler/
      ├── spiders/
      │   ├── schools/           # 院校爬虫
      │   ├── admission/         # 录取数据（按省份分文件）
      │   ├── rankings/          # 排名爬虫
      │   ├── policies/          # 政策爬虫
      │   └── ugc/               # UGC爬虫
      ├── items.py
      ├── pipelines.py
      ├── middlewares.py
      ├── settings.py
      ├── validators.py          # 数据校验规则
      └── proxy_pool.py          # 代理池管理

  Playwright (独立使用):
    适用: 复杂交互（小红书/知乎需要滚动的页面）
    适用: 验证码页面（配合打码平台）

  单页面脚本:
    适用: 一次性采集（教育部名单下载）
    工具: requests + BeautifulSoup4
```

### 8.2 Python 依赖清单

```
# requirements.txt

# 爬虫核心
scrapy>=2.12.0
scrapy-playwright>=0.0.40
playwright>=1.48.0

# HTTP
requests>=2.32.0
httpx>=0.27.0
aiohttp>=3.9.0           # 异步HTTP（批量下载PDF用）

# 解析
lxml>=5.3.0
beautifulsoup4>=4.12.0
parsel>=1.9.0
pdfplumber>=0.11.0
camelot-py[b64]>=0.11.0  # 表格提取
python-docx>=1.1.0
PyMuPDF>=1.24.0

# 数据处理
pandas>=2.2.0
numpy>=1.26.0

# 数据库
psycopg2-binary>=2.9.0
sqlalchemy>=2.0.0
asyncpg>=0.29.0          # 异步PG（爬虫直连）
redis>=5.0.0

# 反爬工具
fake-useragent>=1.5.0

# 代理管理
requests-ip-rotator>=0.2.0

# NLP/内容处理
jieba>=0.42.1
snownlp>=0.12.3          # 情感分析（简单场景）

# LLM辅助
openai>=1.30.0           # 调用DeepSeek API提取结构化数据

# 监控
loguru>=0.7.0

# 工具
python-dotenv>=1.0.0
click>=8.1.0             # CLI工具
rich>=13.0.0             # 终端美化输出
```

### 8.3 项目目录结构建议

```
D:\WorkBuddy\gaokao-database\
├── PLAN.md                           # 本文件
├── README.md
├── .env                              # 数据库连接等敏感配置（不入库）
├── requirements.txt
├── src/
│   ├── crawler/                      # Scrapy项目
│   │   ├── scrapy.cfg
│   │   └── gk_crawler/
│   │       ├── __init__.py
│   │       ├── items.py
│   │       ├── pipelines.py
│   │       ├── middlewares.py
│   │       ├── settings.py
│   │       └── spiders/
│   │           ├── __init__.py
│   │           ├── schools/
│   │           ├── admission/
│   │           ├── rankings/
│   │           ├── policies/
│   │           └── ugc/
│   ├── etl/                          # 数据ETL
│   │   ├── pdf_parser.py
│   │   ├── data_validator.py
│   │   └── data_loader.py
│   ├── api/                          # 数据API（后期）
│   │   ├── app.py
│   │   └── routers/
│   ├── models/                       # SQLAlchemy ORM模型
│   │   ├── base.py
│   │   └── ... 
│   ├── scripts/                      # 运维脚本
│   │   ├── init_db.sql               # 建库建表SQL
│   │   ├── create_partitions.sql     # 创建分区
│   │   ├── import_csv.py             # CSV导入
│   │   └── backup_db.py              # 备份
│   └── utils/
│       ├── proxy_pool.py
│       ├── user_agents.py
│       └── db_utils.py
├── data/
│   ├── attachments/
│   ├── exports/
│   ├── backups/
│   └── raw/
└── tests/
    ├── test_crawlers/
    └── test_validators/
```

### 8.4 快速启动建议

```bash
# 1. 初始化Python环境
cd D:\WorkBuddy\gaokao-database
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt

# 2. 安装Playwright浏览器
playwright install chromium

# 3. 搭建PostgreSQL（本地开发用Docker）
docker run --name gaokao-pg -e POSTGRES_PASSWORD=gaokao123 \
  -e POSTGRES_DB=gaokao_db -p 5432:5432 -d postgres:16

# 4. 初始化数据库表结构
psql -h localhost -U postgres -d gaokao_db -f src/scripts/init_db.sql

# 5. 运行第一个爬虫测试
cd src/crawler
scrapy crawl moe_schools -o data/raw/schools.jsonl

# 6. 数据导入
python src/etl/data_loader.py --input data/raw/schools.jsonl --table base.schools
```

### 8.5 法律与合规注意事项

```
1. 爬虫合规底线：
   - 检查目标网站的 robots.txt
   - 控制采集频率，避免影响网站正常运行
   - 不采集非公开数据（需登录才能查看的）
   - 不采集个人隐私信息（身份证号、联系方式等）
   - 不破解或绕过技术保护措施（反爬 ≠ 技术保护措施，但需谨慎）

2. 数据使用合规：
   - 教育部/考试院的公开数据可以采集使用（政府信息公开条例）
   - 社交媒体数据：公开内容可采集，但不得进行用户画像二次利用
   - 商业数据：有版权的数据不能直接抓取使用

3. 建议做：
   - 数据来源标注（记录每一条数据的来源URL）
   - 数据脱敏（用户ID哈希存储）
   - 保留原始数据的"三七开"：30%来自官方，30%来自社交媒体，40%自购或自产

4. 不建议做：
   - 逆向工程商业APP的私有API
   - 绕过Cloudflare等安全防护
   - 大规模分布式采集（小规模慢速更安全）
```

---

> **下一步建议：** 读完本方案后，建议从 Phase 1 第一步开始，先做数据库搭建和教育部院校数据采集。需要我帮你写 `init_db.sql` 建表脚本，或者先跑通一个院校爬虫Demo吗？
