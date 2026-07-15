# 高考志愿填报数据库 — 数据采集执行规则

> **版本：** v1.0
> **日期：** 2026-06-29
> **依据：** PLAN.md 策划方案
> **用途：** 执行者的操作手册 — 按此规则逐条执行，不做自由发挥

---

## 目录

1. [总则：数据采集的基本原则](#1-总则数据采集的基本原则)
2. [各数据采集任务的执行规则](#2-各数据采集任务的执行规则)
3. [数据校验规则全集（可执行版）](#3-数据校验规则全集可执行版)
4. [各省考试院采集执行细则](#4-各省考试院采集执行细则)
5. [采集任务的工作流](#5-采集任务的工作流)
6. [数据质量门禁](#6-数据质量门禁)
7. [输出物规范](#7-输出物规范)
8. [黄金规则](#8-黄金规则)

---

## 1. 总则：数据采集的基本原则

### 1.1 规则优先级排序

```
第一优先级：合规
├── 采集前检查 robots.txt，任何 disallow 路径不碰
├── 只采集公开页面（不需要登录就能访问的内容）
├── 不采集个人隐私信息（身份证号、手机号、详细地址、学号等）
├── 不对目标网站造成压力（DOWNLOAD_DELAY >= 2s）
└── 数据采集后不做二次售卖

第二优先级：质量
├── 宁可少一条数据，不要一条错误数据
├── 每条数据入库前必须通过校验函数
├── 校验不通过的数据写入 error_records，不入库
└── 同一字段多个源冲突时，以官方源为准

第三优先级：覆盖
├── 先做 Top15 省份，再做全部 31 省
├── 先做近 3 年，再回溯更早年份
└── 先做本科批，再做专科批/提前批
```

### 1.2 铁律（违反即打回）

1. **所有对外使用的数据必须标注 `data_source` 和 `data_confidence`**，缺一不可
2. **不允许在原始数据上做人为修改**——发现数据错误，修正逻辑写在脚本里，留下变更日志，不手动改库
3. **每一批采集完成后，必须出一份批次报告**——统计总数、成功数、失败数、缺失率、异常记录数

### 1.3 统一规范

| 项目 | 规范 |
|------|------|
| 输出格式 | JSON Lines (`.jsonl`)，每行一个独立 JSON 对象 |
| 字段命名 | `snake_case`，全小写 |
| 日期格式 | ISO 8601：`YYYY-MM-DD`，时间戳：`YYYY-MM-DDTHH:mm:ssZ` |
| 空值处理 | 缺失字段用 `null`，不要用空字符串 `""` 或 `"暂无"` |
| 编码 | 统一 UTF-8，无 BOM |
| 换行 | LF（Unix 风格），不用 CRLF |
| 文件命名 | `{spider_name}_{timestamp}.jsonl`，时间戳格式 `YYYYMMDD_HHmmss` |

---

## 2. 各数据采集任务的执行规则

### 2.1 操作卡：院校数据（schools）

**数据来源：**
- 教育部全国高等学校名单（权威源）：`http://www.moe.gov.cn/jyb_xxgk/s5743/s5744/`
- 阳光高考院校库（补充源）：`https://gaokao.chsi.com.cn/sch/`

**从哪里开始采集：**
1. 先手动下载教育部最新高校名单（PDF/Excel），解出 CSV 格式
2. 写一个 Python 脚本来解析这个文件，只提取：`code_edu`, `name`, `province`, `level`, `admin_department`
3. 抽查 10 条数据与官网核对，确认解析正确
4. 再写阳光高考爬虫，补充：`type`, `is_211`, `is_985`, `is_double_first_class`, `website`, `address`, `city` 等字段
5. 小规模测试：只爬 5 所高校的详情页，验证字段解析正确后全量运行

**采集到什么程度算完成：**
- **完成标准：** 涵盖教育部最新名单中全部高校（当前约 3117 所）
- **必填字段：** `code_edu`, `name`, `province`, `level` — 这 4 个字段任一为空，该条记录不合格
- **容错率：** 选填字段（如 `logo_url`, `history`, `tuition_range`）允许缺失 ≤30%
- **数据覆盖校验：** 教育部名单中有多少所，库里至少就要有多少所（允许 ±5 所公差，因为名单发布和爬虫运行可能有时间差）

**采集频率：**
- 首次采集：全量一次性运行，约 1-2 天
- 增量更新：每年 5-6 月（教育部发布新名单后），运行增量脚本
- 非名单年度：仅检测已采集院校的链接是否有效

**异常处理：**
- 教育部官网文件 URL 变更：搜索 `site:moe.gov.cn 高等学校名单` 找新文件
- 阳光高考页面改版：暂停爬虫，手动更新解析规则
- 个别院校页面 404：记录到 `errors.jsonl`，标记 `page_not_found`

---

### 2.2 操作卡：专业目录数据（majors + major_categories）

**数据来源：**
- 教育部本科专业目录：`http://www.moe.gov.cn/s78/A08/gjs_left/moe_1034/`
- 阳光高考专业库：`https://gaokao.chsi.com.cn/zyk/`

**从哪里开始采集：**
1. 先确认最新版本的专业目录（本科 + 专科），从教育部官网下载
2. 解析专业目录文件，提取：`major_id`, `name`, `category_id`, `level`, `study_years`, `degree`
3. 再从阳光高考专业库补充：`description`, `main_courses`, `employment_rate`, `salary_avg`
4. 小规模测试：抽查 5 个专业的全部字段，与教育部目录核对

**采集到什么程度算完成：**
- **完成标准：** 教育部目录中所有本科专业 + 所有专科专业
- **必填字段：** `major_id`, `name`, `category_id`, `level`
- **年度版本：** 每份专业数据必须带 `version_year` 字段

**采集频率：**
- 首次采集：全量一次性运行
- 年度更新：教育部新目录发布后 1 周内完成

---

### 2.3 操作卡：历年录取数据（admission_data）— 核心大表

**数据来源：**
- 各省教育考试院官网（31 省列表见 PLAN.md §3.2）
- 阳光高考录取数据（部分省份）：`https://gaokao.chsi.com.cn/lq/`

**从哪里开始采集：**
1. **先做一个省份 Demo：** 选浙江（最低难度，数据全）`https://www.zjzs.net/`
2. 手动从浙江考试院找到 2024 年普通类一段投档线页面
3. 写爬虫提取该页表格数据（院校+专业+计划+投档分+位次）
4. 抽取 10 条数据与网页手动核对，确认解析正确
5. 确认爬虫逻辑无误后，扩展到浙江近 3 年
6. 浙江验证通过后，再扩展到其他 A 组省份（山东、上海、北京、江苏）
7. A 组全部通过后，扩展到 B 组（陕西、广东、河南等）
8. C 组省份最后做（西藏、青海、新疆等）

**采集到什么程度算完成：**
- **完成标准（分省）：**
  - 该省当年所有批次（本科一批、本科二批、专科批）的所有投档数据
  - 该省省控线数据（`province_score_lines`）
  - 该省一分一段表数据（`score_rank_segments`）
- **容错率：**
  - 缺失率 ≤ 3%（即某省份录取数据缺失不超过 3% 的记录）
  - 关键字段 `school_id`, `province`, `year`, `admit_score_min`, `admit_rank_min` 任一为空 → 该条记录不合格
  - 全年份完成：年序号连续，不得跳年
- **校验确认：** 每个省份完成后，抽取 30 条数据与官网人工核对

**采集频率：**
- 首次采集：一次性跑历史数据（建议从 2020 年回溯到最新发布年份）
- 年度窗口：**每年 6 月下旬至 8 月中旬**（各省陆续公布投档线）
- 年度更新：窗口期内每日检查考试院是否有新公告发布
- 增量更新：仅补当年新数据，不回溯修改历史数据

**异常处理：**
- 考试院网站在录取期间可能特别慢：增加超时时间到 30s，重试间隔拉大
- 投档线以 PDF 发布（如陕西 `sneea.cn`）：用 `pdfplumber` + `camelot` 提取表格
- 表格结构混乱（如河南 `haeea.cn`）：先用正则尝试，如果解析失败 > 30%，标记为_需人工辅助_，暂停自动采集

---

### 2.4 操作卡：省控线 + 一分一段表

**数据来源：** 与录取数据相同来源（各省教育考试院）

**从哪里开始采集：**
1. 同一省份的爬虫里，额外增加两个解析分支
2. 省控线：一般在考试院网站上有单独页面，列明各批次分数线
3. 一分一段表：通常在公布成绩当天（6 月 23-26 日）发布

**采集到什么程度算完成：**
- 省控线：该省当年所有批次线完整（本科一批、本科二批、专科批、艺术类、体育类等）
- 一分一段表：该省当年所有考生类别的完整分段表
- 校验条件：一分一段表最后一档累计人数 = 该省该类别当年实际考生数（误差 ≤ 1%）
- 分数字段：`score_line` 必须 > 0
- 位次字段：`rank_end >= rank_start`

**采集频率：**
- 每年 6 月 23 日-26 日（各省出分窗口）集中采集，优先第一个做
- 过了窗口期的省份，回头从官网历史数据页面找

---

### 2.5 操作卡：招生政策数据（policies）

**数据来源：**
- 各省教育考试院官网 → 招生政策/通知公告栏目
- 教育部官网 → 招生工作规定

**从哪里开始采集：**
1. 先确定采集范围：每个省份最新版（2025/2026年）的《招生工作规定》
2. 再补充：各省志愿填报安排、投档规则说明、录取日程
3. 从教育部层面开始：采集全国性政策（全国招生工作规定）
4. 再依考试院分组采集各省政策

**采集到什么程度算完成：**
- **完成标准：** 31 省 + 教育部的全量招生政策文件
- 每个文件必须包含：`title`, `province`, `year`, `url`, `content_text`
- AI 提取的关键点（`key_points`, `batch_settings`, `policy_changes`）标注为 `auto_extracted`，需人工复核
- 字段 `voting_rule`, `admission_rule` 为必填

**采集频率：**
- 每年 4-6 月（各省发布招生工作规定）集中采集
- 政策变化追踪：每年采集完成后，与上年政策做差异比较

---

### 2.6 操作卡：就业数据（employment_stats）

**数据来源：**
- 各高校就业质量报告（PDF，从各校就业网获取）
- BOSS 直聘研究院年度报告
- 教育部就业白皮书

**从哪里开始采集：**
1. 先从 Top 50 高校开始（211/985 高校就业报告最完整且公开）
2. 构建高校就业网 URL 模板：`https://career.{school_pinyin}.edu.cn/` 或 `https://{school_pinyin}.job.cn/`
3. 搜索关键词：`site:{school_website} 就业质量报告 2024 PDF`
4. 下载 PDF → 用 `pdfplumber` 提取文本 → LLM 提取结构化数据
5. 小规模测试：先做 5 所高校，验证 PDF 解析 + LLM 提取准确率

**采集到什么程度算完成：**
- Phase 1：Top 50 高校的就业质量报告成功提取
- Phase 2：软科排名前 200 的高校
- Phase 3：全部本科院校（选做）
- 关键字段 `employment_rate`, `salary_avg`, `further_study_rate` 至少有一个非空
- 所有提取结果标注提取置信度（`auto_high` / `auto_medium` / `auto_low`）

**采集频率：**
- 每年 10-12 月（各校集中发布年度就业质量报告）

---

### 2.7 操作卡：排名数据（rankings）

**数据来源：**

| 排名 | 起始 URL | 采集方式 |
|------|---------|---------|
| 软科中国大学排名 | `http://www.shanghairanking.cn/rankings/bcur/2025` | Scrapy + HTML |
| 校友会排名 | `https://www.cuaa.net/` | Scrapy + HTML |
| QS 世界大学排名 | `https://www.qschina.cn/university-rankings/` | Scrapy + HTML |
| 教育部学科评估 | 教育部官网 PDF | PDF 解析 |

**从哪里开始采集：**
1. 先做软科排名——数据最完整、页面结构规范、无反爬
2. 从最新年份开始，往前追溯（软科至少 5 年数据）
3. 再做校友会排名
4. 学科评估数据最后做

**采集到什么程度算完成：**
- 每个排名至少包含：`ranking_name`, `ranking_year`, `school_id`, `rank`, `score`
- 排名覆盖完整：缺漏院校不超过参评院校的 5%
- 学科评估：拿到所有公开等级（A+ 到 C-）

**采集频率：**
- 软科：每年发布后 1 周内更新
- 校友会：每年发布后 1 周内更新
- 学科评估：多年一次（有新版发布时更新）

---

### 2.8 操作卡：UGC 用户评价数据（user_reviews + forum_posts）

**数据来源：**

| 平台 | 采集方式 | 优先级 | 风险级别 |
|------|---------|--------|---------|
| 知乎 | Scrapy 爬取公开页面 | Phase 2 | ⚡ 中等 |
| B 站 | 官方 API（`api.bilibili.com`） | Phase 2 | ✅ 低 |
| 百度贴吧 | Scrapy 爬取精华帖 | Phase 3 | ✅ 低 |
| 小红书 | Playwright（谨慎） | Phase 3 | ⚡ 高 |
| 掌上高考 | 公开评价页面 | Phase 2 | ⚡ 中等 |

**从哪里开始采集：**
1. **先做最安全的：** B 站官方 API（有开放接口，无需登录，频率限制宽）
2. 搜索 B 站视频：关键词组合 `高考志愿`、`大学报考`、`专业推荐`、`[具体院校名]`
3. 提取视频评论区内容，匹配关联院校
4. 再做知乎：搜索高赞问答（选择点赞数 > 100 的回答优先采集）
5. 其他平台按优先级逐步加入

**采集到什么程度算完成：**
- B 站：每个 Top 100 高校至少关联 10 条以上视频评论
- 知乎：每个 Top 100 高校至少关联 5 条以上高赞问答
- 每条评价必须标注 `platform`, `platform_url`, `sentiment`
- 用户隐私脱敏：`author_id` 用 MD5 哈希，不存储用户名、头像等

**采集频率：**
- B 站 / 知乎：每季度增量采集一次
- 其他平台：Phase 3 开始，每月一次

**法律红线（违反即暂停整个 UGC 采集线）：**
- 不采集私信、非公开内容
- 不采集用户个人信息（昵称、头像、个人主页 URL）
- 采集内容只做数据分析，不做二次传播或展示
- 严格遵守各平台 `robots.txt` 和 API 使用条款

---

## 3. 数据校验规则全集（可执行版）

以下校验函数可直接复制到 `src/etl/data_validator.py` 中使用。

```python
"""
data_validator.py — 数据校验模块
每条数据入库前必须调对应校验函数通过。
返回空列表表示校验通过，返回错误列表表示不合格。
"""

from typing import Any


def validate_school(record: dict) -> list[str]:
    """校验院校数据"""
    errors = []

    # 必填字段检查
    for field in ["code_edu", "name", "province", "level"]:
        if not record.get(field):
            errors.append(f"[schools] 必填字段缺失: {field}")

    # 字段格式检查
    if record.get("code_edu") and not str(record["code_edu"]).isdigit():
        errors.append(f"[schools] code_edu 必须是数字: {record['code_edu']}")
    if record.get("code_edu") and len(str(record["code_edu"])) != 5:
        errors.append(f"[schools] code_edu 必须是5位数字: {record['code_edu']}")

    if record.get("name") and len(str(record["name"]).strip()) < 2:
        errors.append(f"[schools] name 长度异常: {record['name']}")

    # level 取值范围
    valid_levels = ["本科", "专科", "职业本科"]
    if record.get("level") and record["level"] not in valid_levels:
        errors.append(f"[schools] level 值非法: {record['level']}（合法值: {valid_levels}）")

    # 办学类型取值范围
    valid_types = [
        "综合", "理工", "农林", "医药", "师范", "语言",
        "财经", "政法", "体育", "艺术", "军事", "民族"
    ]
    if record.get("type") and record["type"] not in valid_types:
        errors.append(f"[schools] type 值非法: {record['type']}")

    # 数据来源检查
    if not record.get("data_source"):
        errors.append("[schools] data_source 不能为空")

    return errors


def validate_major(record: dict) -> list[str]:
    """校验专业数据"""
    errors = []

    for field in ["major_id", "name", "category_id", "level"]:
        if not record.get(field):
            errors.append(f"[majors] 必填字段缺失: {field}")

    if record.get("major_id") and len(str(record["major_id"]).strip()) < 2:
        errors.append(f"[majors] major_id 长度异常: {record['major_id']}")

    valid_levels = ["本科", "专科"]
    if record.get("level") and record["level"] not in valid_levels:
        errors.append(f"[majors] level 值非法: {record['level']}")

    if record.get("version_year") and not isinstance(record["version_year"], int):
        errors.append(f"[majors] version_year 必须是整数: {record['version_year']}")

    if not record.get("data_source"):
        errors.append("[majors] data_source 不能为空")

    return errors


def validate_admission(record: dict) -> list[str]:
    """校验录取数据——核心校验函数"""
    errors = []

    # 必填字段
    for field in ["school_id", "province", "year", "student_category"]:
        if not record.get(field):
            errors.append(f"[admission] 必填字段缺失: {field}")

    # 年份合理性
    if record.get("year"):
        year = int(record["year"])
        if year < 2010 or year > 2027:
            errors.append(f"[admission] year 超出合理范围: {year}")
    else:
        errors.append("[admission] year 不能为空")

    # 分数逻辑
    if record.get("admit_score_min") is not None:
        min_score = float(record["admit_score_min"])
        if min_score <= 0:
            errors.append(f"[admission] admit_score_min 必须大于0: {min_score}")
        if min_score > 780:
            errors.append(f"[admission] admit_score_min 超过合理范围: {min_score}（满分一般750）")

    if record.get("admit_score_max") is not None and record.get("admit_score_min") is not None:
        if float(record["admit_score_max"]) < float(record["admit_score_min"]):
            errors.append(f"[admission] admit_score_max < admit_score_min: {record['admit_score_max']} < {record['admit_score_min']}")

    if record.get("admit_score_avg") is not None and record.get("admit_score_min") is not None:
        if float(record["admit_score_avg"]) < float(record["admit_score_min"]):
            errors.append(f"[admission] admit_score_avg < admit_score_min")
    if record.get("admit_score_avg") is not None and record.get("admit_score_max") is not None:
        if float(record["admit_score_avg"]) > float(record["admit_score_max"]):
            errors.append(f"[admission] admit_score_avg > admit_score_max")

    # 位次逻辑
    if record.get("admit_rank_min") is not None:
        rank = int(record["admit_rank_min"])
        if rank <= 0:
            errors.append(f"[admission] admit_rank_min 必须大于0: {rank}")
        if rank > 100_000_000:
            errors.append(f"[admission] admit_rank_min 超出合理范围: {rank}")

    if record.get("admit_rank_max") is not None and record.get("admit_rank_min") is not None:
        if int(record["admit_rank_max"]) < int(record["admit_rank_min"]):
            errors.append(f"[admission] admit_rank_max < admit_rank_min")

    # 计划人数
    if record.get("plan_count") is not None:
        if int(record["plan_count"]) < 0:
            errors.append(f"[admission] plan_count 不能为负数: {record['plan_count']}")
        if int(record["plan_count"]) > 100_000:
            errors.append(f"[admission] plan_count 超出合理范围: {record['plan_count']}")

    # 批次
    valid_batch_prefixes = ["本科", "专科", "提前", "艺术", "体育", "强基"]
    if record.get("batch"):
        has_prefix = any(str(record["batch"]).startswith(p) for p in valid_batch_prefixes)
        if not has_prefix:
            errors.append(f"[admission] batch 值疑似异常: {record['batch']}")

    # 考生类别
    valid_categories = ["文科", "理科", "综合", "物理类", "历史类", "不分文理"]
    if record.get("student_category") and record["student_category"] not in valid_categories:
        errors.append(f"[admission] student_category 值非法: {record['student_category']}")

    if not record.get("data_source"):
        errors.append("[admission] data_source 不能为空")

    return errors


def validate_score_line(record: dict) -> list[str]:
    """校验省控线"""
    errors = []

    for field in ["province", "year", "batch", "student_category", "score_line"]:
        if record.get(field) is None:
            errors.append(f"[province_score_lines] 必填字段缺失: {field}")

    if record.get("score_line") is not None and float(record["score_line"]) <= 0:
        errors.append(f"[province_score_lines] score_line 必须 > 0: {record['score_line']}")

    if record.get("score_line") is not None and float(record["score_line"]) > 780:
        errors.append(f"[province_score_lines] score_line 超出合理范围: {record['score_line']}")

    return errors


def validate_score_rank(record: dict) -> list[str]:
    """校验一分一段表"""
    errors = []

    for field in ["province", "year", "student_category", "score", "cumulative_count"]:
        if record.get(field) is None:
            errors.append(f"[score_rank_segments] 必填字段缺失: {field}")

    if record.get("score") is not None:
        score = float(record["score"])
        if score < 0 or score > 780:
            errors.append(f"[score_rank_segments] score 超出合理范围: {score}")

    if record.get("cumulative_count") is not None and int(record["cumulative_count"]) <= 0:
        errors.append(f"[score_rank_segments] cumulative_count 必须 > 0: {record['cumulative_count']}")

    if record.get("rank_start") is not None and record.get("rank_end") is not None:
        if int(record["rank_end"]) < int(record["rank_start"]):
            errors.append(f"[score_rank_segments] rank_end < rank_start")

    return errors


def validate_policy(record: dict) -> list[str]:
    """校验招生政策"""
    errors = []

    for field in ["title", "province", "year", "url"]:
        if not record.get(field):
            errors.append(f"[policies] 必填字段缺失: {field}")

    if record.get("voting_rule") and record["voting_rule"] not in ["平行志愿", "顺序志愿", "平行志愿+顺序志愿"]:
        errors.append(f"[policies] voting_rule 值非法: {record['voting_rule']}")

    if record.get("admission_rule") and record["admission_rule"] not in ["分数优先", "专业优先", "专业级差"]:
        errors.append(f"[policies] admission_rule 值非法: {record['admission_rule']}")

    return errors


def validate_employment(record: dict) -> list[str]:
    """校验就业数据"""
    errors = []

    if not record.get("school_id") and not record.get("major_id"):
        errors.append("[employment] school_id 和 major_id 至少需要一个")

    if not record.get("year"):
        errors.append("[employment] year 不能为空")
    else:
        year = int(record["year"])
        if year < 2015 or year > 2027:
            errors.append(f"[employment] year 超出合理范围: {year}")

    if record.get("employment_rate") is not None:
        rate = float(record["employment_rate"])
        if rate < 0 or rate > 100:
            errors.append(f"[employment] employment_rate 取值范围应为 0-100: {rate}")

    if record.get("salary_avg") is not None and int(record["salary_avg"]) <= 0:
        errors.append(f"[employment] salary_avg 必须 > 0: {record['salary_avg']}")

    return errors


def validate_ranking(record: dict) -> list[str]:
    """校验排名数据"""
    errors = []

    for field in ["ranking_name", "ranking_year", "school_id", "rank"]:
        if not record.get(field):
            errors.append(f"[rankings] 必填字段缺失: {field}")

    valid_rankings = ["软科中国大学排名", "软科世界大学排名", "校友会排名",
                      "QS世界大学排名", "US News排名", "THE泰晤士排名",
                      "教育部学科评估", "ESI学科排名"]
    if record.get("ranking_name") and record["ranking_name"] not in valid_rankings:
        errors.append(f"[rankings] ranking_name 不在已知列表中: {record['ranking_name']}（如需添加请先更新校验规则）")

    if record.get("rank") is not None:
        r = int(record["rank"])
        if r <= 0:
            errors.append(f"[rankings] rank 必须 > 0: {r}")
        if record.get("rank_total") and r > int(record["rank_total"]):
            errors.append(f"[rankings] rank 不能大于 rank_total: {r} > {record['rank_total']}")

    return errors


def validate_user_review(record: dict) -> list[str]:
    """校验用户评价数据"""
    errors = []

    for field in ["school_id", "platform", "platform_url"]:
        if not record.get(field):
            errors.append(f"[user_reviews] 必填字段缺失: {field}")

    valid_platforms = ["知乎", "小红书", "百度贴吧", "豆瓣", "B站", "掌上高考", "抖音", "快手"]
    if record.get("platform") and record["platform"] not in valid_platforms:
        errors.append(f"[user_reviews] platform 不在已知列表中: {record['platform']}")

    if record.get("sentiment") and record["sentiment"] not in ["positive", "negative", "neutral"]:
        errors.append(f"[user_reviews] sentiment 值非法: {record['sentiment']}")

    if record.get("author_id") and len(str(record["author_id"])) == 0:
        errors.append("[user_reviews] author_id 为空字符串（应使用 MD5 哈希或 null）")

    if record.get("data_source") and "user_reviews" not in str(record["data_source"]):
        pass  # user_reviews 的 data_source 可以不包含表名

    if not record.get("data_source"):
        errors.append("[user_reviews] data_source 不能为空")

    return errors


# ========== 通用批量校验函数 ==========

def validate_batch(records: list[dict], table_name: str) -> dict:
    """
    批量校验数据，返回统计信息。

    参数:
        records: 要校验的数据列表
        table_name: 表名（schools/majors/admission/...）

    返回:
        {
            "total": int,           # 总记录数
            "passed": int,          # 通过数
            "failed": int,          # 失败数
            "pass_rate": float,     # 通过率
            "failed_records": list, # 失败记录（含索引和错误原因）
            "error_summary": dict   # 错误类型统计
        }
    """
    VALIDATORS = {
        "schools": validate_school,
        "majors": validate_major,
        "admission": validate_admission,
        "province_score_lines": validate_score_line,
        "score_rank_segments": validate_score_rank,
        "policies": validate_policy,
        "employment": validate_employment,
        "rankings": validate_ranking,
        "user_reviews": validate_user_review,
    }

    validator = VALIDATORS.get(table_name)
    if not validator:
        return {"error": f"未知表名: {table_name}，可用表名: {list(VALIDATORS.keys())}"}

    passed = 0
    failed = 0
    failed_records = []
    error_summary = {}

    for idx, record in enumerate(records):
        errors = validator(record)
        if errors:
            failed += 1
            failed_records.append({
                "index": idx,
                "record_id": record.get("id", record.get("major_id", record.get("code_edu", idx))),
                "errors": errors,
            })
            for err in errors:
                err_type = err.split("]")[0] + "]" if "]" in err else "通用"
                error_summary[err_type] = error_summary.get(err_type, 0) + 1
        else:
            passed += 1

    total = len(records)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total * 100, 2) if total > 0 else 0,
        "failed_records": failed_records,
        "error_summary": error_summary,
    }
```

---

## 4. 各省考试院采集执行细则

### 4.1 分组规则

| 组别 | 省份 | 特征 | 采集工具 | DOWNLOAD_DELAY | 验证方式 |
|------|------|------|---------|---------------|---------|
| **A 组** | 浙江、山东、上海、北京、江苏、天津、辽宁、黑龙江、重庆、四川、福建、湖北、陕西 | HTML 表格完整、数据公开好 | Scrapy | 2s | 抽 10 条人工核对 |
| **B 组** | 广东、河北、山西、内蒙古、安徽、江西、河南、湖南、广西、海南、贵州、云南、甘肃、宁夏 | 有 JS 渲染/PDF 发布/表格不规范 | Scrapy + Selenium / pdfplumber | 3s | 抽 30 条人工核对 |
| **C 组** | 吉林、西藏、青海、新疆 | 数据稀少、格式特殊 | 人工下载 + 辅助脚本 | — | 全量人工核对 |

### 4.2 执行步骤（每省通用模板）

```
步骤 1：确认数据存在
  - 手动访问考试院官网，找到投档线/录取数据页面
  - 记录 URL 和页面结构特征
  
步骤 2：写测试爬虫
  - 只爬 1 条数据 → 打印原始 HTML → 验证解析规则
  - 如果成功，爬 1 个完整页面的数据 → 逐条人工核对
  - 如果失败率 > 20%，回到步骤 1 重新分析页面结构
  
步骤 3：全量运行
  - 启动完整爬虫，输出到 .jsonl 暂存文件
  - 运行完毕后立即运行 validate_batch()
  
步骤 4：校验
  - pass_rate >= 95% 且 error_summary 中没有致命错误 → 允许入库
  - pass_rate < 95% → 检查错误模式，修复爬虫逻辑后重跑
  
步骤 5：入库
  - 校验通过的数据 → 批量导入 PostgreSQL
  - 校验失败的数据 → 写入 errors_jsonl，生成采集报告
```

### 4.3 各省特殊处理备忘

| 省份 | 特殊处理 |
|------|---------|
| **浙江** | `zjzs.net` 数据最全，每年有完整 CSV/Excel 下载，优先手工下载 |
| **山东** | `sdzk.cn` 按批次分多个页面发布，需聚合处理 |
| **陕西** | `sneea.cn` 投档线以 PDF 发布，用 pdfplumber + camelot 提取表格 |
| **河南** | `haeea.cn` 表格含合并单元格，需 pandas 后处理 |
| **上海** | 3+3 模式，`student_category` 为"综合"，与 3+1+2 省份不同 |
| **北京** | `bjeea.cn` 一分一段表数据完整，可选做主要验证集 |
| **吉林** | `jleea.com.cn` 格式不规范，数据量少，建议人工下载辅助 |

### 4.4 采集时序（年度）

```
5月      6月           7月           8月           9月+
 |        |             |             |             |
 |     6/7 高考      6/23-26     7-8月各省     补漏 + 
 |     考前准备      出分+省控线  陆续发布       数据校验
 |                   一分一段表    投档线
 |                     ↓           ↓
 |                 优先级最高    第二批采集
 |                 （采集窗口最短） （窗口约2个月）
```

---

## 5. 采集任务的工作流

### 5.1 流程图（文字版）

```
┌─────────────────────────────────────────────────────────────────┐
│                      〖 数据采集工作流 〗                        │
└─────────────────────────────────────────────────────────────────┘

                          ┌─────────────┐
                          │ ① 数据发现   │
                          │（检测新数据   │
                          │  发布/收到通知)│
                          └──────┬──────┘
                                 │
                                 ▼
                          ┌─────────────┐
                          │ ② 任务创建   │
                          │（记录到       │
                          │  crawl_tasks) │
                          └──────┬──────┘
                                 │
                                 ▼
                          ┌─────────────┐
                          │ ③ 爬虫      │
                          │  开发/配置   │
                          └──────┬──────┘
                                 │
                                 ▼
                          ┌─────────────┐
                          │ ④ 小规模    │        ┌───────────────┐
                          │  测试验证    │◄───────│ 通过？        │
                          │  (爬1页/     │  否    │ 修复解析规则  │
                          │   检查输出)   │        └───────────────┘
                          └──────┬──────┘
                                 │ 是
                                 ▼
                          ┌─────────────┐
                          │ ⑤ 全量运行   │
                          │ (输出到 raw/ │
                          │  暂存文件)   │
                          └──────┬──────┘
                                 │
                                 ▼
                          ┌─────────────┐
                          │ ⑥ 数据校验   │
                          │ (validate_   │
                          │  batch())    │
                          └──────┬──────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                通过/合格                 不通过/不合格
                    │                         │
                    ▼                         ▼
          ┌──────────────────┐     ┌──────────────────┐
          │ ⑦ 写入主表       │     │ ⑦ 写入 errors   │
          │ (UPSERT入库)     │     │ (打回修复)       │
          └──────┬───────────┘     └────────┬─────────┘
                 │                          │
                 ▼                          ▼
          ┌──────────────────┐     ┌──────────────────┐
          │ ⑧ 记录元数据     │     │ ⑧ 生成错误分析   │
          │ (data_change_log │     │ → 回到步骤③     │
          │  + 标记版本)     │     │   或标记为"需    │
          └──────┬───────────┘     │   人工辅助"      │
                 │                 └──────────────────┘
                 ▼
          ┌──────────────────┐
          │ ⑨ 存档原始数据   │
          │ (raw/ 目录 +     │
          │  批次报告)       │
          └──────────────────┘
```

### 5.2 每个步骤的产出物

| 步骤 | 产出物 | 说明 |
|------|--------|------|
| ① 数据发现 | 一条日志记录 + 通知 | 记录发现时间、来源URL、数据类型 |
| ② 任务创建 | `crawl_tasks` 表记录 | 记录任务名称、URL、策略、频率 |
| ③ 爬虫配置 | spider Python 文件 | 放在 `src/crawler/gk_crawler/spiders/` 下 |
| ④ 测试验证 | 测试输出 JSON + 验证记录 | 小规模数据 + 人工核对结果 |
| ⑤ 全量运行 | `raw_{timestamp}.jsonl` | 原始采集数据，存入 `data/raw/{data_type}/{year}/` |
| ⑥ 数据校验 | 校验结果 JSON + `errors_{timestamp}.jsonl` | `validate_batch()` 输出结果 |
| ⑦ 入库 | PostgreSQL 表数据 + 日志 | UPSERT 写入，记录变更日志 |
| ⑧ 元数据 | `data_change_log` 记录 | 记录操作类型、变更内容 |
| ⑨ 存档 | `{batch_name}_report.md` | 批次采集报告 |

---

## 6. 数据质量门禁

### 6.1 以下情况数据必须打回，不允许入库

```yaml
致命错误（一票否决）:
  - 某个省份的录取数据整体缺失率 > 5%
    # 例如：某省2024年招生的本科院校应约100所，如果入库 < 95所，整批打回
  - 记录的关键字段至少一个为空:
    - school_id, province, year, admit_score_min, admit_rank_min
    # 缺少任一关键字段，该条记录直接丢弃，不写入主表
  - 违反基本一致性校验:
    - admit_score_max < admit_score_min（最高分 < 最低分）
    - admit_rank_max < admit_rank_min（最高位次 < 最低位次）
    - admit_score_min > 780（分数超过合理范围）
    - admit_rank_min > 100_000_000（位次超出合理范围）
  - data_source 字段为空
    # 每一条数据必须标明来源，用于后续追溯和冲突仲裁
  - 同一记录多个数据源冲突且无法仲裁
    # 例如：浙江考试院说A校最低分600，阳光高考说650，两个源都无法确认孰对
    # → 两条都暂时不入库，标记为"冲突-待仲裁"

严重错误（批次打回）:
  - 批次验证通过率 < 95%
    # 通过率 = 通过校验的记录数 / 总记录数
  - 同一年份同一省份的批次线不连续
    # 例如有2024年"本科一批"线但没有"本科二批"线，需确认
  - 一分一段表最后一档累计人数与公布考生数差异 > 3%
    # 说明分段表数据可能不完整或解析出错

警告（允许入库但标记）:
  - 选填字段（如description, history, tuition_range）缺失率 > 30%
    # 允许入库，但在采集报告中明确标注缺失率
  - 数据来自非官方源且置信度为 low
    # 在 data_confidence 字段标记为 low，UI 层面做区分显示
  - AI 自动提取的内容（就业报告、政策摘要）
    # 标注为 auto_extracted，后续需人工复核
```

### 6.2 门禁执行流程

```python
def quality_gate(records: list[dict], table_name: str, batch_config: dict) -> dict:
    """
    质量门禁检查 — 在入库前执行
    
    返回:
        {
            "decision": "pass" | "reject" | "pass_with_warnings",
            "reasons": [...],
            "stats": {...}
        }
    """
    result = validate_batch(records, table_name)
    
    # 一票否决检查
    if result["total"] == 0:
        return {"decision": "reject", "reasons": ["没有数据"]}
    
    pass_rate = result["pass_rate"]
    reasons = []
    
    # 致命：通过率低于 95%
    if pass_rate < 95:
        reasons.append(f"通过率 {pass_rate}% 低于阈值 95%")
    
    # 致命：关键字段缺失比例
    key_fields = ["province", "year", "data_source"]
    missing_key_rate = sum(
        1 for r in records if any(r.get(f) is None for f in key_fields)
    ) / len(records)
    if missing_key_rate > 0.05:
        reasons.append(f"关键字段缺失率 {missing_key_rate*100:.1f}% 超过 5%")
    
    # 致命：一致性冲突
    if table_name == "admission":
        conflict_count = sum(
            1 for r in records
            if r.get("admit_score_max") is not None
            and r.get("admit_score_min") is not None
            and float(r["admit_score_max"]) < float(r["admit_score_min"])
        )
        if conflict_count > 0:
            reasons.append(f"存在 {conflict_count} 条分数逻辑冲突记录")
    
    # 判定
    if reasons:
        return {"decision": "reject", "reasons": reasons, "stats": result}
    
    # 检查是否存在警告
    warnings = []
    if result["failed"] > 0:
        warnings.append(f"{result['failed']} 条数据校验失败（已写入 errors）")
    
    decision = "pass" if not warnings else "pass_with_warnings"
    return {"decision": decision, "reasons": reasons + warnings, "stats": result}
```

---

## 7. 输出物规范

### 7.1 目录结构

数据采集完成后，每个批次应输出以下文件到指定目录：

```
D:\WorkBuddy\gaokao-database\data\
├── raw\                                    # 原始采集数据
│   ├── schools\
│   │   ├── raw_{YYYYMMDD_HHmmss}.jsonl     # 原始数据
│   │   └── errors_{YYYYMMDD_HHmmss}.jsonl  # 校验失败数据
│   ├── majors\
│   │   ├── raw_{YYYYMMDD_HHmmss}.jsonl
│   │   └── errors_{YYYYMMDD_HHmmss}.jsonl
│   ├── admission\
│   │   ├── 2024\
│   │   │   ├── 广东\
│   │   │   │   ├── raw_{YYYYMMDD_HHmmss}.jsonl
│   │   │   │   └── errors_{YYYYMMDD_HHmmss}.jsonl
│   │   │   ├── 浙江\
│   │   │   └── ...
│   │   ├── 2023\
│   │   └── ...
│   ├── score_rank\                        # 一分一段表
│   ├── policies\
│   ├── employment\
│   ├── rankings\
│   └── user_reviews\
│
├── attachments\                            # 文件附件
│   ├── school_logos\
│   ├── employment_reports\
│   └── policy_files\
│
└── exports\                                # 数据导出
```

### 7.2 日志文件

```
logs\
├── {spider_name}_{YYYYMMDD_HHmmss}.log       # 爬虫运行日志
├── validation_{YYYYMMDD_HHmmss}.log          # 校验结果日志
└── quality_gate_{YYYYMMDD_HHmmss}.log        # 质量门禁日志
```

### 7.3 批次报告模板

```markdown
# 数据采集批次报告

**任务名称：** {batch_name}
**数据类型：** {data_type}
**执行时间：** {execution_time}
**数据来源：** {data_source_url}

## 采集概况

| 指标 | 数值 |
|------|------|
| 计划采集数 | 1000 |
| 实际采集数 | 997 |
| 成功入库 | 985 |
| 校验失败 | 12 |
| 通过率 | 98.7% |
| 耗时 | 3h 24min |

## 错误类型分布

| 错误类型 | 数量 | 占比 |
|---------|------|------|
| admit_score_min 缺失 | 5 | 41.7% |
| province 为空 | 3 | 25.0% |
| admit_score_max < min | 2 | 16.7% |
| batch 值非法 | 2 | 16.7% |

## 数据质量评估

- 整体质量等级：**合格** / ⚠️ 需注意 / ❌ 不合格
- 注意事项：
  - 省份 X 的数据缺失率 3.2%（受限于该省PDF格式特殊）
  - 建议人工复核省份 Y 的 5 条异常高分记录

## 下次建议

- {建议内容，如：补充省份Z的数据}
- {如涉及改版，记录改版特征}
```

---

## 8. 黄金规则

以下 5 条是执行过程中最容易踩坑的地方，贴在屏幕前：

### 规则 1：永远从官方源开始

> **先做教育部名单，再做考试院数据，最后才是第三方和UGC。**
>
> 官方源的字段可以作为后续数据质量的"基准线"。非官方数据与官方数据冲突时，无条件以官方数据为准，把冲突记录写入 `data_change_log` 并标记。

### 规则 2：每次只改一个变量

> **写爬虫时不要同时改省份和采集方式。**
>
> 正确做法：先用 A 组某个省份跑通 Scrapy 基础流程 → 保持采集方式不变，换到另一个 A 组省份 → 确认兼容性后，再尝试切换到 B 组（可能需要加 Selenium）。一次只改一个变量，遇到问题更容易定位。

### 规则 3：原始数据永远不改

> **从网页/PDF/API 采集到的原始信息，保持原样写入 `.jsonl`，入库时再做清洗和转换。**
>
> 不要在爬虫里做"看起来合理的修正"——比如觉得某个字段应该是整数就做了 `int()` 转换，结果原始数据里写的是"约600"。原始数据是唯一可追溯的证据，污染了就回不去了。

### 规则 4：每年都是全新的一年

> **不要假设去年的爬虫今年还能跑。**
>
> 考试院网站每年都可能改版、换域名、改表格结构。每年录取季开始前（5 月底），花一天时间检查所有 A 组省份的爬虫是否还工作。每年至少预留 20% 的时间用于修复"上年能跑今年跑不了"的情况。

### 规则 5：数据入库后不要直接在前端展示

> **数据经过校验≠数据没有异常值。**
>
> 一条校验通过的录取记录最低分是 750（满分），位次是 1（省状元），这在校验规则里是合法的。但如果在 UI 上展示，需要业务逻辑层做二次过滤。入库是数据团队的职责，前端展示加必要的保护是开发团队的职责——中间加一层 API，API 负责做对外展示的过滤和格式化。

---

> **执行顺序建议：**
>
> 1. 先看完 PLAN.md（策划方案）了解全景
> 2. 再看本 RULES.md（执行规则）了解每步怎么做
> 3. 从 Phase 1 开始：建库 → 院校数据 → 专业目录 → Top15 省份录取数据
> 4. 每一步完成后出批次报告
> 5. 每省完成后做一次质量门禁检查
