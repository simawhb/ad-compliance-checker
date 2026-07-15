# 驷马报考 — 项目执行计划

> 最后更新：2026-06-30 17:15
> 状态：平稳运行期

---

## 一、已配置的定时任务

### 任务1：每日数据积累（每天凌晨3:00）
**cron 表达式：** `0 3 * * *`
**项目ID：** `驷马报考-每日巡检`

| 执行内容 | 产出 | 数据量/天 |
|----------|------|-----------|
| B站论坛巡检 | `data/raw/forum/bilibili/YYYY-MM-DD.jsonl` | ~170 条 |
| 智联招聘采集 | `data/raw/employment/jobs/zhaopin_YYYY-MM-DD.jsonl` | ~300 条 |
| 网站巡检 | `reports/daily/YYYY-MM-DD_report.md` | 3 URL |
| 数据导入 | 自动写入 `data/simadb/gaokao.db` | — |

### 任务2：省份投档线采集（7月15日凌晨3:00）
**cron 表达式：** `0 3 15 7 *`
**项目ID：** `驷马报考-省份投档线采集`

| 执行内容 | 说明 |
|----------|------|
| 采集山东2026投档线 | 已配置province_admission_spider |
| 采集广东2026投档线 | 同上 |
| 采集北京2026投档线 | 同上 |
| 采集陕西2026投档线 | 同上 |
| 导入SQLite | 运行 import_to_sqlite.py |

> 注意：部分省份投档线可能7月下旬才发布，如果跑出来为0，等下一次手动重跑。

---

## 二、项目路线图

### 第1阶段：基础建设（已完成 ✅）
- [x] 建库建表
- [x] 院校数据采集（2,952所）
- [x] 专业目录采集（378个）
- [x] 数据校验模块
- [x] 任务管理系统

### 第2阶段：数据积累（进行中 ⏳）
- [x] 浙江录取数据（21,419条）
- [x] B站论坛每日巡检
- [x] 智联招聘每日采集
- [x] 省份考试院通用爬虫框架
- [ ] **7月15日**：山东/广东/北京/陕西投档线采集
- [ ] **8月**：补充其他A组省份录取数据

### 第3阶段：产品化（已完成 ✅）
- [x] SQLite数据库（24,000+条）
- [x] FastAPI接口层（7个接口）
- [x] Vue3前端（引导式首页/院校对比/专业详情/AI问答）
- [x] AI Agent（自然语言查询）
- [x] PRD产品需求文档

### 第4阶段：上线运营（待启动）
- [ ] PostgreSQL迁移（SQLite并发不够时）
- [ ] 云服务器部署
- [ ] 域名+HTTPS
- [ ] 线下推广（结合本地资源）

---

## 三、数据量预估（6个月后）

| 数据集 | 当前 | 6个月后 | 预计存储 |
|--------|------|---------|---------|
| 院校库 | 2,952 | 2,952 | 不变 |
| 录取数据 | 21,419（浙江） | 10万+（5省） | 约50MB |
| B站口碑 | 172 | **3万+** | 约30MB |
| 智联招聘 | 15 | **5.4万+** | 约10MB |
| **总计** | **24,000+** | **18万+** | **<100MB** |

> SQLite 完全撑得住 100MB 数据量。等超过 500MB 再考虑 PostgreSQL。

---

## 四、快速启动

```bash
# 启动Web服务
cd D:\WorkBuddy\gaokao-database && python src/api/app.py

# 手动跑省份采集
python src/crawler/gaokao_spiders/spiders/admission/province_admission_spider.py --province 山东 --year 2026

# 手动跑B站巡检
python src/crawler/gaokao_spiders/spiders/forum/bilibili_forum_patrol.py

# 手动跑智联招聘
python src/crawler/gaokao_spiders/spiders/employment/job_collector_final.py
```

---

## 五、数据导入SQLite

```bash
cd D:\WorkBuddy\gaokao-database && python src/scripts/import_to_sqlite.py
```
