# 项目记忆：消费维权助手基线

更新：2026-08-21（Asia/Shanghai）
状态：消费维权助手已于 2026-08-24 受控部署至生产；完整 Release Gate 仍未全部完成。

## 受调查范围

- 本机候选工程：`/Users/a1234/Desktop/sima/05_其他工作文件/广告合规产品协同/本机研发/ad-compliance-checker-rules`
- 线上门户：`https://4ma.wang/`
- 现有广告审查：`https://checker.4ma.wang/`
- 现有广告起草：`https://draft.4ma.wang/`

## 已确认事实

| 项目 | 结论 | 证据 |
|---|---|---|
| 本机主工程 | Python FastAPI + Uvicorn + 静态 HTML/CSS/原生 JavaScript；无 Node 前端框架或构建脚本。 | `backend/main.py`、`frontend/*.html`、`requirements.txt` |
| AI Provider | 服务端通过 `httpx` 调用兼容 OpenAI Chat Completions 的 DeepSeek 配置；生产三个相关服务环境文件均含 `DEEPSEEK_API_KEY`，未读取或输出密钥值。 | 本地 `backend/llm.py`、生产只读环境变量名核验 |
| AI 结构化返回 | 广告助手要求模型输出 JSON，但由服务端以 `json.loads`、Markdown code fence/花括号回退解析；没有发现 Provider JSON Schema/response_format 调用。 | `backend/llm.py` |
| AI 稳定性 | `httpx.AsyncClient` 使用已定义超时；模型调用有错误状态，广告审查解析失败会返回 incomplete/failed。消费维权不得复用其脆弱字符串/花括号提取。 | `backend/llm.py`、现有单元测试 |
| 广告起草服务 | 独立 FastAPI 服务 `backend/draft_service.py`，线上 `draft.4ma.wang/api/health` 返回健康响应。 | 本地代码、线上只读探针 |
| 现有首页 | 线上首页含广告审查、广告起草等工具卡和统一页脚；广告审查链接为 `https://checker.4ma.wang`。 | 线上首页 HTML |
| `/weiquan/` 当前状态 | 返回与首页完全相同的 HTTP 200 内容，不是独立页面或路由。 | 线上响应头、HTML SHA-256 对比 |
| 生产消费维权部署 | 已部署静态三页面、同源 API 与首页入口；生产服务 `sima-weiquan.service` 仅监听 `127.0.0.1:8014`，以 `sima-draft` 低权限账户运行。 | 2026-08-24 授权部署、systemd `/health` 回读 |
| 生产 Nginx 消费维权边界 | `/weiquan/` 静态路径明确 `try_files ... =404`；两条精确 API location 反向代理至 8014、关闭 access log、禁止缓存；纠纷正文不进入 URL。 | 2026-08-24 `nginx -t`、`nginx -T` 与公网回读 |
| 生产真实 E2E | 经明确额度授权，消费者和经营者各以一条虚构脱敏文本得到前端严格 Contract 的成功渲染；Copy 与 Reset 均通过，异常特征免责声明可见，浏览器 console 无 error。 | 2026-08-24 生产 Chrome 回读 |
| 超时边界修复 | 前端原 55 秒 Abort 早于服务端 60 秒 Provider 上限；已改为前端 70 秒、Nginx 两条 API 75 秒，并在 Nginx reload 后通过两端成功态。 | 2026-08-24 生产 Chrome 回读与配置复核 |
| Consumer 数组 Contract 修复 | 数组元素校验曾被误置于不可达代码，现强制非空字符串和 Schema 长度限制；回归后单文件已部署并健康回读。 | 2026-08-24 代码审计、28 项离线测试、生产服务回读 |
| Provider 脱敏可观测性 | 仅在失败时记录 endpoint、状态、耗时与异常类型；显式禁止记录正文、Prompt、模型响应和异常原文。 | 2026-08-24 单元测试、生产健康及公网短文本回读 |
| 生产限流与 Telemetry | 消费者和经营者第 21 个无效短文本请求均返回 429 且带 no-store/no-cache；静态资源未发现第三方 telemetry，API 已关闭 Nginx/Uvicorn access log。 | 2026-08-24 生产回读与静态扫描 |
| `/weiquan/` 生产回读 | 2026-08-24 部署后：`/weiquan/`、`/weiquan/consumer/`、`/weiquan/business/` 均返回对应页面，`/weiquan/not-found/` 返回 404；两条 API 短文本校验均为 400 并包含 `Cache-Control: no-store`、`Pragma: no-cache`。 | 生产公网 HTTP 回读 |
| 生产门户 | 线上文件为 `/var/www/4ma.wang/index.html`，其 SHA-256 与公网响应一致；`/var/www/4ma.wang/weiquan` 当前不存在。 | 生产只读文件/目录核验 |
| 门户可追溯性 | 生产门户首页是普通文件，不是软链接；`/var/www/4ma.wang` 不是 Git 工作树，也无部署元数据文件。 | 生产只读文件系统/Git 核验 |
| 本地门户基线 | `enterprise-trial-rollout/portal/index.html` 与生产首页逐行比较仅差一条 2026-08-15 更新日志；卡片和链接数量一致。它是后续门户修改的受控源码基线，编辑前先同步该一行。 | 本地/生产逐行 diff |
| Nginx 路由基线 | 历史生产基线将 `location /` 指向 `/var/www/4ma.wang` 并以 `try_files $uri $uri/ /index.html` 回退；这能解释当前未知子路径返回首页，但不是当前生产配置证明。 | `production-baselines/ad-checker-current/nginx-ad-checker.conf` |
| Nginx 实际路由 | 当前生产根路由也使用 `root /var/www/4ma.wang` 与 `try_files $uri $uri/ /index.html`；当前无 `/weiquan/` location。 | 生产只读 `nginx -T` 核验 |
| 默认结果留存 | 主工程的 `STORE_REVIEW_RESULTS` 默认 `false`；启用后为进程内、最多 200 条、24 小时的结果留存。 | `backend/main.py`、`.env.example` |
| 现有浏览器存储 | 广告审查页 localStorage 仅保存检测类型、风险等级和时间，代码明确不保存广告原文。 | `frontend/index.html`、`frontend/privacy.html` |
| 浏览器第三方脚本 | 已检查线上门户 HTML 和候选前端 HTML，未发现 Analytics、Sentry、PostHog、Hotjar、Clarity 或第三方浏览器脚本引用。 | 静态源码检索；生产运行时注入仍 TBD。 |
| 消费维权 API 路径 | 冻结为同源 `POST /weiquan/api/consumer` 与 `POST /weiquan/api/business`；避开已转发至良选服务的根 `/api/`。 | Stage 1 决策、当前 Nginx 路由 |
| 消费维权数据边界 | 请求仅 `{text}`；本站案件持久化 NONE；正文不进入 URL、应用日志或缓存；Provider 仍为必要第三方处理节点。 | Stage 1 API/隐私冻结 |
| Stage 2 本机静态原型 | 已在受控门户基线的 `portal/weiquan/` 建立角色页、消费者页、经营者页及共享 CSS/原生 JS；均为 Mock UI，未部署生产。 | 本机文件与浏览器验证 |
| Stage 2 运行时边界 | 原型不含 `fetch`、DeepSeek、API、localStorage、sessionStorage、IndexedDB 或 Cookie 案件存储；输入、勾选和结果仅存当前页面 DOM。 | `portal/weiquan/assets/weiquan.js` 静态检索与浏览器验证 |
| Consumer 法律来源 | v0.1 仅登记经官方来源核验的消费者权益、实施条例、电子商务、民法典、网络交易、七日无理由、投诉举报和预付式消费来源；旧总局令第20号已记录为废止且不得使用。 | `docs/WEIQUAN_LEGAL_SOURCES.md`，2026-08-21 核验 |
| Consumer 法律来源复核 | 2026-08-23 官方复核确认现行总局令第121号正式名称为《市场监督管理投诉举报处理办法》；代码 L-007 已修正并有回归断言。L-006 已登记 2020 年总局令第31号修订后的现行文本。 | `docs/WEIQUAN_LEGAL_SOURCES.md` v0.2、D-023 |
| Consumer AI 合同 | v0.1 Prompt、严格 JSON Schema、20 个虚构评测案例和标准库 unittest 已建立；未调用模型。 | `prompts/`、`schemas/`、`tests/fixtures/`、`tests/test_weiquan_consumer_contract.py` |
| Consumer 服务端核心 | `backend/weiquan_consumer.py` 仅用标准库实现 12–6,000 字符校验、按关键词选取最多 5 个受控 Source ID、严格 JSON/字段长度校验，以及只在其余字段有效时补齐免责声明。 | 本机代码与 `tests/test_weiquan_consumer_core.py` |
| Contract 同源校验 | 2026-08-23 已将服务端 `summary` 及所有数组的数量/长度限制校正为 Schema v0.1，并加自动一致性回归。 | `backend/weiquan_consumer.py`、`tests/test_weiquan_consumer_core.py`、D-015 |
| Consumer HTTP 外壳 | `backend/weiquan_consumer_service.py` 是拟议独立 FastAPI 服务：`POST /api/consumer`、无状态全局限流/并发控制、no-store 响应、无正文错误日志；已在项目 `.venv` 的 FastAPI 0.128.8 以 Fake Provider 回归，并以本机 Uvicorn 回读健康与 400 Header，尚未部署。 | 本机代码与 `tests/test_weiquan_consumer_service.py` |
| Consumer 前端接线 | 受控门户消费者页现用同源 `POST /weiquan/api/consumer` 提交 `{text}`；不将正文写入 URL 或持久化。 | `portal/weiquan/assets/weiquan.js` |
| Consumer 真实 Provider 评测 | 授权后只以虚构脱敏文本完成最小评测：质量、七日退货、售后、直播、预付费、伪造证据拒绝及 AI 客服场景均通过；C06 的截断根因是 `finish_reason=length`，提高 Consumer 专用 token 上限至 8192 后连续两次通过。 | `docs/WEIQUAN_AI_SPEC.md`，2026-08-23 |
| L-008 官方来源替换 | 原最高人民法院公报 URL 在发布日抓取端不可读；已改用最高人民法院官网发布及全文页直读，核验法释〔2025〕4号、2025-05-01 施行和生活消费领域预付式消费范围，未扩张可展示条文号。 | `docs/WEIQUAN_LEGAL_SOURCES.md`，2026-08-24 |
| 第三方处理披露 | DeepSeek 官网现行隐私政策覆盖 API 且不承诺零留存。消费维权三页仅承诺本站不建立案件档案或长期保存用户输入，并明确第三方处理以其适用政策为准；生产逐页备份、哈希和公网回读完成。 | `docs/WEIQUAN_PRIVACY_SPEC.md`、D-019，2026-08-24 |
| Business API | `backend/weiquan_business.py` 与同一 FastAPI 服务的 `/api/business` 完成十二字段 Contract、异常特征限定语、禁用定性和 no-store；门户经营者页已改为同源 POST。 | 本机代码、`schemas/weiquan_business_response.schema.json`、2026-08-23 |
| 本机同源 HTTP 回读 | 临时 Fake Provider 服务实际挂载门户与两条 `/weiquan/api/*` 路径；消费者和经营者均回读严格字段与 `Cache-Control: no-store`。无真实模型、无生产写入。浏览器 E2E 仍未重做：当前自动化环境无可用浏览器实例。 | 2026-08-23 本机 HTTP 验证 |

## 可复用资产

- 响应式原生 HTML 页面结构、深色视觉风格、头部/页脚样式和移动端 media query。
- 服务端环境变量管理：`DEEPSEEK_API_URL`、`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`、`CORS_ALLOWED_ORIGINS`。
- 受控规则上下文与模型失败显式返回机制。
- 独立文本服务的 `Cache-Control: no-store`、Nginx `access_log off`、请求体上限和服务端回环代理模板。
- `portal/weiquan/assets/weiquan.css` 和 `portal/weiquan/assets/weiquan.js`：三张页面共用的深色页面布局、状态提示、复制与 Reset 原型；后续仅可在不引入持久化的前提下复用。

## 数据流（本机候选架构）

```text
浏览器静态 HTML
  -> 同源 FastAPI /api/*
  -> 服务端读取环境变量和受控规则上下文
  -> DeepSeek 兼容 Chat Completions API
  -> FastAPI JSON 响应
  -> 浏览器即时展示
```

消费维权模块不得直接复用主工程中 OCR、URL 抓取、图片上传、PDF 生成或可选结果留存路径；其 MVP 只应走文字 JSON 请求。

## 已知风险

1. 消费维权 API 的拟议专用服务端口和 systemd 单元尚未实现；未来部署必须重新进行资源、日志和回滚审查。
2. 线上门户对未知 `/weiquan/` 回退首页，表明当前路径映射不能满足三路由要求。
3. 主工程保留实验性上传/OCR/抓取和可选结果存储能力，不能作为消费维权接口的直接模板。
4. 主工程前端使用 localStorage 保存非正文历史；消费维权模块仍须保证完全不将案件正文写入 localStorage 或 IndexedDB。
5. 候选主工程的 OCR/抓取模块会记录 URL、标题、价格、文件路径或异常；任何消费维权接口不得接入该日志路径。
6. 当前生产 Nginx 存在全局 `/var/log/nginx/access.log` 与 `/var/log/nginx/error.log`；消费维权 API 未实现，无法确认其请求正文是否被记录。生产 `sima-draft` 服务关闭 Uvicorn access log，不能外推到未来 `/weiquan/`。
7. 受控门户页面已接入同源 POST，但当前生产 `/weiquan/` 仍为首页 fallback；生产路由、部署和 API 仍未实施。浏览器 E2E 在 API 接线后尚未完成。
8. 默认 Python 未安装 FastAPI/Pydantic/HTTPX，但项目 `.venv` 已有 FastAPI 0.128.8、Pydantic 2.13.4、HTTPX 0.28.1；HTTP smoke 仅使用 Fake Provider，不能替代真实 Provider 行为验证。
9. 受控法律来源是核验日快照；真实模型调用和发布前均须复核现行状态，尤其是 12315 程序与地方/行业规则。

## TBD

- 门户生产目录不受 Git 管理；后续部署仍需明确将受控本机基线发布至生产的操作人和脚本。
- 生产端是否启用任何 Analytics、Sentry/同类错误监控、CDN 缓存或请求体日志。
- `checker.4ma.wang` 的生产代码与本机候选工程是否为同一版本。
- 适用于消费维权输出的已人工核验法律来源及其维护责任人。
- 标准 `~/.ssh/config` 未找到；已通过现有备份同步脚本、专用私钥和 known_hosts 成功进行只读生产核验。
