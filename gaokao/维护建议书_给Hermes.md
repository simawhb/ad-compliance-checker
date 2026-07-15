# 驷马报考 gaokao-database 项目维护建议书

> **致：** Hermes Agent  
> **来源：** Claude Code 代码审查（2026-07-04）  
> **主题：** 代码审查发现的问题、已修复项及后续维护建议

---

## 一、项目健康总览

| 维度 | 评分 | 说明 |
|------|------|------|
| 安全性 | ⚠️ 需持续关注 | API Key 已迁移到 .env，但无用户认证体系 |
| 实用性 | ⚠️ 基础修复完成 | 编码、路径、连接管理等问题已修复 |
| 数据覆盖 | 🔴 薄弱 | 仅浙江 2024 年录取数据完整，其他省份几乎空白 |
| 商业就绪 | 🔴 早期 | 无用户系统、无付费墙、无品牌露出（已初步添加） |

---

## 二、已发现并修复的问题

### P0 — 安全与编码（已修复，无需再动）

| 问题 | 严重程度 | 修复方式 | 涉及文件 |
|------|---------|---------|---------|
| DeepSeek API Key 硬编码在 app.py:39 | 🔴 高危 | 迁移到 `.env` 文件，通过 `python-dotenv` 加载 | `app.py`、新增 `.env.example` |
| DEEPSEEK_KEY.txt 明文存 Key | 🔴 高危 | 已废弃该文件，改为说明文字 | `DEEPSEEK_KEY.txt` |
| 中文编码混乱，大量乱码 | 🔴 阻塞使用 | 统一 UTF-8 编码策略，JSON 响应强制 `charset=utf-8` | `app.py` |
| CORS `allow_origins=["*"]` | 🟡 中危 | 改为从 `CORS_ORIGINS` 环境变量读取，默认仅本机 | `app.py` |
| `reload=True` 用于生产 | 🟡 中危 | 改为 `RELOAD` 环境变量控制 | `app.py` |
| `check_same_thread=False` 无保护 | 🟡 中危 | 引入 contextvars 连接池，协程安全 | `app.py` |

### P1 — 工程实用性问题（已修复）

| 问题 | 严重程度 | 修复方式 | 涉及文件 |
|------|---------|---------|---------|
| `import_to_sqlite.py` 路径写死 `src/data/raw/` | 🟡 中 | 兼容 `data/raw/` 和 `src/data/raw/` 两套路径 | `import_to_sqlite.py` |
| 每次请求新建 SQLite 连接，无连接池 | 🟡 中 | contextvar 连接池 + HTTP 中间件自动管理生命周期 | `app.py` |
| `daily_run.py` 引用未定义的 `logger` | 🟡 中 | 统一使用 `logging.getLogger()` | `daily_run.py` |
| 无 `.gitignore` | 🟢 低 | 新增，排除 .env/.db/__pycache__ 等 | 新增 `.gitignore` |
| 无 `requirements.txt` | 🟢 低 | 新增核心依赖清单 | 新增 `requirements.txt` |
| 无健康检查端点 | 🟢 低 | 新增 `GET /api/health` | `app.py` |
| DeepSeek API 无限流/无重试 | 🟡 中 | 添加令牌桶限流 + 指数退避重试 | `app.py` |

### P2 — 数据覆盖（已修复或框架就绪）

| 问题 | 说明 | 状态 |
|------|------|------|
| 省控线硬编码在 app.py | 已改为从 DB 读取，app.py 不再存数据 | ✅ |
| 仅 4 省省控线 | 迁移脚本扩展到 **31 省市区**全量数据 | ✅ |
| 迁移脚本功能单一 | 增强为 CLI：支持 `--province`、`--from-json`、`--export-json`、`--clear`、`--list` | ✅ |

---

## 三、尚未修复的问题（需 Hermes 持续维护）

### 🔴 高优先级

#### 1. 数据覆盖严重不足
- **现状**：录取数据仅有浙江 2024 年（`src/data/raw/admission/zhejiang/2024/`）完整，其他省份几乎空白
- **建议**：
  ```bash
  # 优先采集陕西本地数据（种子用户）
  python src/crawler/gaokao_spiders/spiders/admission/province_admission_spider.py --province 陕西 --year 2026

  # 运行省控线迁移（已有 31 省数据）
  python src/scripts/migrate_control_lines.py
  ```
- **原因**：你在西安，陕西考生是产品最直接的种子用户

#### 2. 两个 `raw` 目录并存的混乱
- **现状**：`data/raw/` 和 `src/data/raw/` 两套目录同时存在，部分数据在 A 目录，部分在 B 目录
- **建议**：统一迁移到 `data/raw/`（规范路径），删除 `src/data/raw/` 下的重复文件
  ```bash
  # 检查哪些文件在 src/data/raw/ 下而 data/raw/ 下没有
  diff <(cd src/data/raw && find . -type f) <(cd data/raw && find . -type f)
  # 手动迁移后删除 src/data/raw/
  ```

#### 3. 爬虫任务从未实际执行
- **现状**：`config/crawl_tasks.json` 中所有任务的 `last_run_at`、`last_status`、`next_run_at` 全为 null
- **建议**：
  ```bash
  # 手动运行一次验证爬虫是否可用
  python src/scripts/task_manager.py run moe_schools
  # 成功后检查 crawl_tasks.json 会更新状态
  ```
  如果爬虫本身有 bug 一直失败，需要修复爬虫代码或移除此 JSON 文件改用直接调用

### 🟡 中优先级

#### 4. HTML 前端 API 字段不匹配
- **现状**：前端 `index.html` 中多处使用旧 API 响应字段名（如 `d.results` 而非 `d.data`、`d.lines` 而非 `d.data`）
- **建议**：用浏览器打开页面后，在 Network 面板对比 API 实际返回的 JSON 字段名与前端代码使用的字段名，逐项校正

#### 5. 生产环境部署检查项
```bash
# 部署前必须确认：
# 1. 创建 .env 文件
cp .env.example .env
# 编辑 .env，填入真实 API Key，设置 CORS_ORIGINS 和 RELOAD=false

# 2. 确保数据库存在且有数据
python src/scripts/migrate_control_lines.py

# 3. 启动服务
python src/api/app.py

# 4. 验证健康检查
curl http://127.0.0.1:8000/api/health
```

#### 6. SQLite 到 PostgreSQL 的迁移
- **现状**：`init_db.sql` 已设计 PostgreSQL 架构，但实际运行在 SQLite
- **建议**：数据量增长到百万级后执行迁移
- 迁移策略：SQLite 导出 → ETL 清洗 → PostgreSQL 导入

### 🟢 低优先级（长期规划）

#### 7. 用户系统
- 当前全匿名，无认证鉴权
- 如果需要收费或做使用量统计，需要引入用户系统

#### 8. 多模型冗余
- 当前 AI 问答仅依赖 DeepSeek API
- 建议增加备用模型（如本地 Ollama 或 Moonshot），服务不可用时自动切换

#### 9. 隐私政策合规
- 已创建静态页面 `/static/privacy.html`
- 如采集用户数据（不仅仅是公开数据），需要补充用户协议

---

## 四、日常维护清单

### 每日巡检
```bash
python src/scripts/daily_run.py
```

### 数据导入（有新数据源时）
```bash
python src/scripts/import_to_sqlite.py
```

### 省控线更新（每年 6 月出分后）
```bash
# 编辑 migrate_control_lines.py 更新 CONTROL_LINES_DATA 中的分数
# 然后执行：
python src/scripts/migrate_control_lines.py --clear
```

### 启动服务
```bash
cd D:/WorkBuddy/gaokao-database
pip install -r requirements.txt --break-system-packages
python src/api/app.py
# 访问 http://127.0.0.1:8000
```

---

## 五、修改文件清单（本次代码审查）

```
新增文件：
  .env.example             环境变量配置模板
  .gitignore               排除规则
  requirements.txt         依赖清单
  src/api/static/privacy.html  隐私政策页

修改文件：
  src/api/app.py           全面重写（安全+编码+连接池+限流+CORS+日志）
  src/api/DEEPSEEK_KEY.txt 改为废弃说明
  src/api/static/index.html 添加 footer 品牌信息 + 隐私链接
  src/scripts/import_to_sqlite.py  路径兼容修复
  src/scripts/daily_run.py         logger 修复 + 配置优化
  src/scripts/migrate_control_lines.py  重写（31省+CLI+导入导出）
  src/scripts/monitor_data.py      路径兼容修复
  README.md                添加变更日志章节
```

---

*本建议书基于 2026-07-04 代码审查生成，后续维护中发现新问题请补充更新。*
