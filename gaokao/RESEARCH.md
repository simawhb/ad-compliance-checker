# 驷马报考 — 竞品调研报告

> 调研时间：2026-06-29
>
> 调研范围：GitHub 开源项目、国内商业产品、互联网大厂布局、行业背景

---

## 一、GitHub 开源项目

### 1.1 直接相关（高考志愿填报系统）

| 项目 | Stars | 描述 | 可借鉴之处 | 不足 |
|------|-------|------|-----------|------|
| [charlieJ107/gaokao](https://github.com/charlieJ107/gaokao) | 中等 | 开源免费的高考志愿查询系统。从 OCR 图片提取录取数据，爬取广西等省份数据 | OCR 处理管线思路；完全免费的定位值得借鉴 | 数据依赖 OCR，脏数据问题严重；只覆盖广西一个省 |
| [tvvshow/gokao](https://github.com/tvvshow/gokao) | 较少 | Go 微服务架构的高考志愿填报系统。后端 Go + Vue 前端 + C++ 推荐算法 | Go 微服务 + CGO 集成 C++ 推荐模块 | 代码量大、架构重；前后端分离开发成本高 |
| [wonbest/GaoKao](https://github.com/wonbest/GaoKao) | 较少 | 高考志愿推荐系统。TypeScript + React + Mobx + Spring + MySQL | 前后端架构可参考 | Spring 生态重，不是 Python 栈 |
| [Jsoneft/gaokao-zhiyuan](https://github.com/Jsoneft/gaokao-zhiyuan) | 较少 | Go 语言开发的高考志愿填报 API。ClickHouse 数据库，高性能查询 | ClickHouse 用于历史录取数据查询的思路；接口设计规范 | 偏后端 API 层 |
| [electronic-pig/gkvr_system](https://github.com/electronic-pig/gkvr_system_frontend) | 较少 | 高考志愿推荐系统（前后端分离） | UI 设计可参考 | 课设级别，代码质量一般 |
| [wonderslife/college-major4hs](https://github.com/wonderslife/college-major4hs) | 较少 | 辽宁物理类考生的本地志愿填报系统，V2 版含 SQLite 本地数据库 | 离线 SQLite 方案可参考 | 仅限辽宁一省 |
| [sgblizzard/gaokao-volunteer-assistant](https://github.com/sgblizzard/gaokao) | 较少 | 一个本地运行的高考志愿推荐程序。读取 SQLite，位次法匹配"冲稳保" | 位次法的推荐逻辑 | 无数据采集能力 |

### 1.2 数据分析类工具

| 项目 | 描述 | 可借鉴之处 |
|------|------|-----------|
| [lyscf/gaokao-analytics](https://github.com/lyscf/gaokao-analytics) | Python + Flask 爬虫，采集录取分数线、招生计划 | 爬虫逻辑设计、数据 API 封装 |
| [vasthan/gaokao-crawler](https://github.com/vasthan/gaokao-crawler) | 爬取全国大学历年高考录取分数的小工具 | 爬虫结构清晰，Java 版 |
| [mumigha/school_Statistics](https://github.com/mumigha/school_Statistics) | 大学爬虫，采集招生计划、录取分数线、省控线 | 数据字段设计可以参考 |
| [toString122/entry-score](https://github.com/toString122/entry-score) | 爬取近几年大学各专业录取分数线 | 专业分数线采集思路 |
| [sdgedfegw/Gaokao-score-distribution](https://github.com/sdgedfegw/Gaokao-score-distribution) | **1996-2024 年全国高考分段表 CSV 数据集（1101 份）** | ⭐ 可以直接使用的一分一段表数据！最成熟的开源数据集项目 |

### 1.3 高校信息 / AI 类

| 项目 | 描述 | 可借鉴之处 |
|------|------|-----------|
| [gaokao-mentor-wisdom](https://github.com/dongsheng123132/gaokao-mentor-wisdom) | 张雪峰语录结构化 JSON 知识库（105条，6个分类） | 结构化存储 AI 建议的思路 |
| [HackSing/gaokao-volunteer-research](https://github.com/HackSing/gaokao-volunteer-research) | 高考志愿研究的 Codex Skill，具备 research 流程 | 数据查证 + 候选方案生成的研究框架 |
| [OpenLMLab/GAOKAO-Bench](https://github.com/OpenLMLab/GAOKAO-Bench) | LLM 在高考题目上的评测基准 | 数据清理后可用作考试难度分析 |
| [open-compass/GAOKAO-Eval](https://github.com/open-compass/GAOKAO-Eval) | LLM 高考评测框架 | 同上 |
| [jnMetaCode/gaokao-college-advisor](https://github.com/jnMetaCode/agency-agents-zh/blob/main/specialized/gaokao-college-advisor.md) | 高考志愿填报 Agent 定义 | Agent prompt 设计逻辑 |
| [education-skills](https://github.com/flysheep-ai/education-skills) | Claude Code 教育类 Skill 集合（K-12 辅导） | 相关但不直接 |

### 1.4 可复用的工具库

| 项目 | 用途 |
|------|------|
| [gaokao-crawler](https://github.com/vasthan/gaokao-crawler) | 爬虫参考 |
| [scrapy](https://scrapy.org/) | 我们主力框架 |
| [pdfplumber](https://github.com/jsvine/pdfplumber) | PDF 表格提取 |
| [camelot-py](https://github.com/camelot-dev/camelot) | PDF 表格精确提取 |

### 开源项目总结

**最有价值的发现：**

1. **[sdgedfegw/Gaokao-score-distribution](https://github.com/sdgedfegw/Gaokao-score-distribution)** — 直接有一分一段表 CSV 数据集可用，1996-2024 年
2. **[charlieJ107/gaokao](https://github.com/charlieJ107/gaokao)** — 完全开源免费的志愿查询系统，OCR 处理路线可参考，但数据质量问题严重（项目方自己承认）→ 说明：**数据质量是核心壁垒**
3. 所有爬虫类项目（lyscf/vasthan/mumigha/toString122）都是单点采集，没有系统性数据管理 → 我们做系统性采集+数据质量管控，本身就有差异化

---

## 二、商业产品分析

### 2.1 头部玩家

| 产品 | 公司 | 模式 | 价格 | 核心能力 |
|------|------|------|------|---------|
| **峰学蔚来** | 张雪峰 | 强 IP 驱动的 1v1 真人咨询 | ¥12,999-¥18,999 | 张雪峰个人IP、团队300+高报师 |
| **优志愿** | 优志愿 | SaaS + B2B2C | ¥298-¥598（卡） | 数据最全、B 端（900+教育机构使用） |
| **掌上高考** | 中国教育在线 | 免费+增值 | 免费/¥99+ | 数据权威（官方背景）、用户量大 |
| **百年育才** | 新三板上市 | 线上+线下 | ¥3,000-¥8,000 | AI + 人工结合，毛利率 89% |
| **完美志愿** | 高考志愿APP | 线上 + B端合作 | - | 数据覆盖全，毛利率 78% |
| **旭德教育** | 新三板上市 | 一对一咨询 | - | 毛利率 78% |

### 2.2 互联网大厂布局

| 大厂 | 产品 | 形态 | 特点 |
|------|------|------|------|
| **百度** | AI志愿助手 | 搜索功能内嵌 | 用户量最大（8.48亿人次服务），免费 |
| **阿里巴巴（夸克）** | 夸克高考 | APP功能 | 近两年大力投入，免费+AI预测 |
| **腾讯** | 新高考通 | 微信/QQ端 | 连接高校端，to B方案 |
| **字节/抖音** | 高考主会场 | 平台活动 | 视频内容的流量打法 |
| **网易有道** | 有道领世志愿 | APP | 霍兰德测评+AI推荐 |
| **作业帮/猿辅导** | - | - | 近年入局，以免费流量吸引 |

### 2.3 商业产品核心发现

1. **数据同质化严重** — 几乎所有产品都基于阳光高考+考试院的标准数据，核心字段都一样。差别在算法推荐和额外服务上
2. **盈利天花板低** — 纯线上产品很难赚钱（优志愿成立 10 年才 B 轮），毛利最高的是 1v1 真人咨询（峰学蔚来模式）
3. **张雪峰是唯一靠个人 IP 驱动的** — 其他人都是靠数据+技术壁垒
4. **我们"专业口碑交叉验证 + 地域招聘关联"的方向，目前市面没有产品在做**

---

## 三、市场背景

- 高考报名人数：2023 年 1291 万，2024 年 1342 万，持续增长
- 市场规模：2016 年 1.3 亿 → 2024 年 10.2 亿 → 预计 2027 年 12.2 亿
- 现有相关企业：约 1850+ 家，80% 成立于近 5 年
- 市场渗透率：不足 10%（还有巨大增长空间）
- 竞争格局：极度分散，没有垄断性选手

**关键判断：** 这个市场不缺"查分数"的产品，缺的是**深度分析型产品**——尤其是"真实口碑 × 就业数据 × 录取数据"的交叉分析。

---

## 四、对我们的启示

| 发现 | 对我们的启示 |
|------|-------------|
| 所有开源项目数据质量差 | 我们 RULES.md 的质量管控体系就是核心优势 |
| 商业产品都只做官方数据 | 论坛口碑 + 招聘数据的交叉分析是蓝海 |
| 峰学蔚来靠个人 IP | 我们做产品而不是做个人 IP，模式更轻、可复制 |
| 大厂做免费，小厂做咨询 | 我们做数据库底层 + API 输出，可以两手抓 |
| 开源有一分一段表数据集 | 可以直接拿过来的数据，省了前期重复劳动 |

**短期可复用成果：**
- [sdgedfegw/Gaokao-score-distribution](https://github.com/sdgedfegw/Gaokao-score-distribution) 的一分一段表 CSV → 直接入库
- [gaokao-mentor-wisdom](https://github.com/dongsheng123132/gaokao-mentor-wisdom) 的张雪峰语录知识库 → 作为 AI 辅助素材
- [HackSing/gaokao-volunteer-research](https://github.com/HackSing/gaokao-volunteer-research) 的研究流程 → 参考做我们自己的数据验证框架
