# 消费维权助手开发计划

更新：2026-08-21（Asia/Shanghai）

## 当前阶段：Stage 3 — Legal Knowledge Baseline + Consumer AI Contract & Evaluation Baseline

### Stage 3 目标

- 建立经官方来源核验的 Consumer 法律来源、Prompt、严格 JSON Schema 与虚构评测集。
- 固化事实纪律、程序边界、法律幻觉防护、输入限制与版本/回归规则。
- 不调用模型、不创建 API、不改 UI/Nginx、不部署生产，也不开发 Business AI。

### Stage 3 修改范围

- `docs/`：受控来源、AI 规范、Contract 增补及决策记录。
- `prompts/`、`schemas/`、`tests/fixtures/`、`tests/`：Consumer 静态质量基线。

### 禁止范围

- 不创建 FastAPI endpoint、Nginx/systemd 配置、门户 UI 或部署产物。
- 不调用模型服务，不上传文件，不引入依赖，不改广告审查助手或开发 Business AI。

### 验收标准

- 所有 Consumer 法律来源均有官方 URL、核验日期、有效状态与可引用范围；不确定来源明确 `TBD — DO NOT USE`。
- Prompt、Schema、fixtures 与静态验证可回归；没有真实 AI、API、持久化或未核验法律条文。

## 阶段状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| Stage 0 基线调查 | READY | 已通过生产只读核验和逐行比较确认门户源码基线；`/weiquan/` 尚未实现，属于后续开发范围。|
| Stage 1 IA/API 边界冻结 | PASS | 门户哈希已与生产回读一致；路由、API、隐私与 UI Shell 范围已冻结。|
| Stage 2 静态 UI 原型 | PASS | 本机静态三页、共享资产和交互闭环已验证；未部署生产。|
| Stage 3 Consumer 法律与 AI 基线 | PASS | 官方来源、Prompt、Schema、20 个虚构评测用例和静态 Contract 验证已建立；未调用模型。|
| Stage 4—12 | 未开始 | 不得跳过前置 Gate。|

## 本轮指令文件状态

| 文件 | 状态 |
|---|---|
| `消费维权助手_Codex_完整开发规范.md`（根目录或 `docs/`） | 未找到；本轮以用户当前指令及已提供的完整项目规范为准。|
| `AGENTS.md`（项目根目录） | 未找到；`libang-custom/AGENTS.md` 存在，但属于嵌套旧企业定制副本，未作为门户/消费维权项目指令采纳。|
| `CODEX_START_HERE.md`、`WORKFLOW.md` | 未找到。|
| `docs/DECISIONS.md`、`docs/DESIGN_SYSTEM.md` | 未找到；不在 Stage 0 擅自补造决策或设计规范。|

## Stage 0 Gate

- [x] 未修改业务代码。
- [x] 已确认本地广告审查项目技术栈及独立起草服务。
- [x] 已确认本地 AI 调用链与默认结果留存开关。
- [x] 已找到线上首页入口和广告审查/起草入口。
- [x] 已检查现有响应式 HTML 页面。
- [x] 已执行现有单元测试、编译、diff 检查与本地 smoke。
- [x] 已记录 TBD 和 Blocker。
- [x] 已确认门户源码基线及 `/weiquan/` 的真实路由/部署归属。
- [x] 已确认生产 Nginx 日志、静态门户 CSP/第三方脚本和缓存边界；新接口日志策略仍为实现前置条件。
- [x] 已确认现有广告工具的隐私/免责声明来源；消费维权声明需独立实现。

**结论：BASELINE READY。**

### 基线同步

已将生产首页中唯一缺失的 2026-08-15 促销活动方案更新日志同步到本机门户基线；未改动卡片、链接、布局或其他 HTML。

## Stage 1 Gate

- [x] 已知门户漂移已同步。
- [x] 已完成本机/生产哈希回读。
- [x] 三路由、消费者/经营者流程与双维度判断已冻结。
- [x] API、数据生命周期、日志、缓存、Nginx 路由及 404 行为已冻结。
- [x] 广告审查联动、Stage 2 状态和法律层边界已冻结。
- [x] MVP 非范围已再次冻结。
- [x] 未实现真实业务功能或改动生产。

**结论：STAGE 1 PASS — IA & API BOUNDARY READY。**

## Stage 2 Gate

- [x] 已建立 `/weiquan/`、`/weiquan/consumer/`、`/weiquan/business/` 本机静态页面。
- [x] 已复用一套共享 CSS/原生 JavaScript；无前端框架或新依赖。
- [x] 两端均有 Empty、Typing、Loading、Success Mock、Validation、Error、Provider unavailable、Copy success 与 Reset 状态。
- [x] 证据清单仅存在当前 DOM；代码检索未发现 localStorage、sessionStorage、IndexedDB、Cookie、fetch 或 AI Provider 调用。
- [x] 浏览器已验证复制、重置、长结果及 320/375/390/430/768/Desktop 无页面级横向滚动。
- [x] 未改生产 Nginx、未创建业务 API、未部署生产。

**结论：STAGE 2 PASS — STATIC UI PROTOTYPE READY。**

### Stage 2 实测记录

- 本机静态服务：`python3 -m http.server 4173 --directory enterprise-trial-rollout/portal`；三页及两个共享资产均返回 HTTP 200。
- 浏览器：角色入口、消费者与经营者输入/校验/Loading/Success、清单勾选、复制、Reset、广告审查外链、Error、Provider unavailable 均已在本机验证；控制台无 error。
- 响应式：使用浏览器 CDP 设备度量在 320、375、390、430、768、1280px 重载消费者长结果；每个宽度均无页面级横向滚动。角色页与经营者长结果另在 320px 验证。
- 不可用质量命令：系统未安装 `node` 或 `pytest`，因此 JS CLI syntax check、项目 pytest、Node build/lint/typecheck 记录为 **NOT AVAILABLE**，不写 PASS。

## Stage 3 Gate

- [x] 建立 Consumer 受控法律来源 v0.1；核心条目均为官方来源，含核验日期、效力层级、状态和引用范围。
- [x] 识别并排除已于 2026-04-15 废止的《市场监督管理投诉举报处理暂行办法》；使用现行第121号令。
- [x] 建立 Consumer Prompt v0.1，含角色、事实、程序、安全、法条、注入和协商函规则。
- [x] 建立严格 JSON Schema v0.1，保留 Stage 1 十字段 Contract，强制免责声明且禁止自由 Markdown。
- [x] 建立 20 个虚构评测案例，覆盖正常、信息不足、消费者可能无理、安全拒绝、程序误区、法律幻觉和 Prompt Injection。
- [x] 建立标准库 Contract 静态验证；未调用模型、未创建 API、未改 UI/Nginx、未部署、未开发 Business AI。

**结论：STAGE 3 PASS — LEGAL & CONSUMER AI BASELINE READY。**

## Stage 4 建议范围

1. 在已冻结的 `POST /weiquan/api/consumer` 同源边界实现纯文字服务端 API；不实现 Business API。
2. 以 v0.1 受控片段、Prompt 和 Schema 接入现有服务端 DeepSeek 调用方式，严格 no-store、无正文日志、限流与超时。
3. 仅使用本阶段虚构 fixtures 做安全的非生产模型回归；验证 parse/validate/normalize、Provider 错误与端到端 UI 状态。

## Stage 4 — Consumer Server API（本机验收通过，未部署）

### Goal

实现已冻结的消费者端纯文字同源 API，复用服务端 DeepSeek 调用边界，并对 Provider 输出执行受控来源、严格 JSON 与隐私保护验证。不得实现经营者 API 或上线。

### In Scope

- `backend/weiquan_consumer.py`：无状态输入校验、受控来源选择、Prompt 组合、严格响应校验与免责声明补齐。
- `backend/weiquan_consumer_service.py`：拟议 `POST /api/consumer` 服务外壳、`no-store`、无正文日志、全局内存限流/并发限制。
- 受控门户消费者页面以同源 `POST /weiquan/api/consumer` 接线；经营者端继续保持 Mock。
- 使用虚构 fixture 与 Fake Provider 做离线回归，并在授权后以虚构、脱敏案例做最小真实 Provider 验证；不保存完整输出。

### Out of Scope

- 生产 Nginx/systemd、部署、Business API、数据库、上传、账号、历史、RAG、法规新增或广告助手改动。

### Gate

- [x] 请求只含 `{ "text" }`，仅以 POST JSON body 传输。
- [x] 输入限制为去空白后 12–6,000 字符；不静默截断。
- [x] 输出仅接受严格 JSON、无 Markdown fence、无未知字段；仅在其余字段有效时补齐标准免责声明。
- [x] 受控法律 Source ID 必须属于本次服务端注入集合。
- [x] API 设计包含 `Cache-Control: no-store`、`Pragma: no-cache` 与不含正文的错误响应。
- [x] 应用代码不记录 request body、Prompt、模型原始响应或函件正文。
- [x] 消费者前端仅同源 POST；经营者端未越级接入真实 AI。
- [x] 已在项目 `.venv` 的 FastAPI 0.128.8 环境以 Fake Provider 完成 HTTP 成功、400、502、503 回归；另以本机 Uvicorn 实际启动回读 `/health` 200 和短文本 400 的 no-store Header；未发起真实模型调用。
- [x] 已新增 Schema/服务端校验同源回归；连同既有 LLM 回归在内，当前选定套件共 22 项离线测试通过。
- [x] 已完成授权范围内的真实 Provider 最小评测：商品质量、七日无理由、售后拒绝、直播宣传、预付式消费及伪造证据请求均通过严格 Schema。
- [x] C06（AI 客服无法转人工）经 `max_tokens=8192` 修正后连续两次通过严格 Schema；无自动重试、无自由文本降级。
- [ ] **Release Blocker：** 生产路由、同源反向代理、systemd、实际日志/缓存边界、浏览器端到端和发布审查仍未执行，须按后续阶段和单独授权处理。

## Business MVP — Local API Acceptance PASS（未部署）

- [x] 冻结十二字段 Schema、Prompt 与同源 `POST /weiquan/api/business` 边界。
- [x] 实现双维判断、异常特征限定语、合规自查、正式回复函和严格来源/安全校验。
- [x] 经营者页面已改为同源 POST；广告宣传审查仍仅链接既有工具。
- [x] Fake Provider HTTP Contract、无正文日志/no-store 与三个虚构脱敏真实 Provider 场景通过。
- [ ] **Release Blocker：** 生产路由、同源代理、浏览器端到端、实际日志/缓存和发布审查尚未执行。

## Local Same-Origin Verification — HTTP Contract PASS（未部署）

- [x] 以临时本机 FastAPI 外壳挂载受控门户和 Fake Provider；未调用 DeepSeek、未使用真实案件文本、未写入生产。
- [x] `POST /weiquan/api/consumer` 与 `POST /weiquan/api/business` 均实际返回对应严格 Contract，并返回 `Cache-Control: no-store`。
- [x] 已移除消费者、经营者页面遗留的“静态原型 / 不发送真实请求”表述，使正常页面文案与已接入的同源 POST 行为一致。
- [ ] **TBD / Release Blocker：** 当前自动化环境无可用浏览器实例，未能重新完成真实浏览器提交、渲染、复制与 Reset 验收；此前 Stage 2 的纯静态浏览器记录不能替代 API 接线后的浏览器 E2E。生产路由、代理、日志、缓存和发布审查仍未执行。

## Legal Source Reverification — v0.2（本机完成，未部署）

- [x] 只读复核官方来源：现行市场监管总局令第121号自 2026-04-15 施行，原第20号令同时废止；第121号令的正式名称不含“暂行”。
- [x] 更正模型受控上下文 L-007 名称，并新增回归断言；不允许旧名称回流。
- [x] L-006 更新为 2020 年总局令第31号修订后的现行文本；未新增未经核验的条文号。
- [ ] **Release Blocker：** 该次复核不替代发布前逐条来源审计、生产日志/缓存核验及浏览器 E2E。

## Privacy & Security Local Audit（本机完成，未部署）

- [x] 两端页面与 API 静态复核：无案件正文浏览器持久化、无文件上传、无账号/案件历史、无第三方 Analytics 或错误监控脚本。
- [x] 两条 API 的正文保持在 POST body；后端 `no-store`/`no-cache` 仅覆盖消费维权路径。
- [x] 消除共享 `LLMClient` 对 Provider 异常文本和模型解析失败片段的日志输出，并增加合成敏感文本不入日志的回归测试。
- [ ] **Release Blocker：** 本机审计不能确认生产 Nginx/CDN/错误监控/Provider 留存；API 接线后的浏览器 E2E 和生产实际日志、缓存审计仍未完成。

## Offline Adversarial Output Guard（本机完成，未部署）

- [x] 消费者、经营者输出校验均增加对伪造/篡改证据、销毁/隐匿证据、隐瞒违法事实、曝光施压及虚报损失等明确不安全操作的拒绝。
- [x] 以虚构字符串完成消费者伪造证据、消费者曝光施压、经营者销毁证据的离线回归；命中后不回传模型内容。
- [ ] **TBD：** 真实 Provider 的完整 C01–C10、B01–B10、Prompt Injection 与浏览器端到端回归尚未形成发布证据；未经新的额度授权不追加真实模型调用。

## Frontend Invalid Response Fallback（本机完成，未部署）

- [x] 消费者与经营者页面在渲染前复核固定字段、类型、未知字段与标准免责声明；不以自由 Markdown 或缺字段结果填充 UI。
- [x] 响应不合格时以 502 路径展示 Provider unavailable，不显示不完整结果或函件。
- [x] Node VM 合成 Contract 测试覆盖完整消费者对象通过、缺少函件字段拒绝；未触发网络或写入存储。
- [ ] **TBD：** 浏览器实例不可用，尚未在 API 接线后的真实页面交互中复验该状态。

## Business & Adversarial Test Matrix（本机完成）

- [x] 建立 `docs/WEIQUAN_TEST_CASES.md`：C01–C20、B01–B10、HTTP/隐私/UI 回归及证据等级统一登记。
- [x] 明确区分 Offline、Model 与 Browser E2E；本机断言不冒充真实模型或生产结论。
- [ ] **Release Blocker：** 完整 Model 回归、Browser E2E、生产配置与发布回读未完成。

## Static UI Shell Regression（本机完成）

- [x] 新增标准库静态门禁：三路由与共享资产存在、角色入口固定、输入页标签/状态/免责声明、同源 POST/no-store 与禁止浏览器案件存储。
- [ ] **TBD：** 静态门禁不能替代浏览器交互、移动端视觉或生产路由验收。

## Static Responsive & Accessibility Baseline（本机完成）

- [x] 静态门禁覆盖 44px 触控基线、可见键盘 Focus、长函件换行、640px 单列布局与减弱动画偏好。
- [ ] **TBD：** 320/375/390/430/768px 的真实浏览器布局、中文输入法与 Copy 操作仍需 Browser E2E。

## Release Review Baseline（文档完成，发布未开始）

- [x] 建立 `docs/WEIQUAN_RELEASE_CHECKLIST.md`，生产路由、代理、缓存、日志、Provider、法律、模型、E2E、响应式、安全与工程证据逐项列明。
- [x] 冻结结论语义：任一 Gate 无生产证据，必须写 `RELEASE BLOCKED`。
- [ ] **Release Blocker：** 所有生产类证据均未收集；本阶段没有修改生产。

### 生产只读基线回读（2026-08-24）

- [x] 生产 `/var/www/4ma.wang/weiquan` 仍不存在；公网 `/weiquan/` 仍回退门户首页。
- [x] 生产 Nginx 仍未配置 `/weiquan/api/consumer`、`/weiquan/api/business` 精确 location；现有根 fallback 仍存在。
- [x] 本次仅 SSH 只读核验，未上传、未修改 Nginx、未创建服务或重启进程。

### 受控生产部署（2026-08-24）

- [x] 经明确授权，先创建生产备份 `/opt/backups/weiquan-20260824-124813`，再上传已验收的静态页面、服务端代码和受控 Prompt。
- [x] 创建 `sima-weiquan.service`：仅监听 `127.0.0.1:8014`、使用既有服务端 DeepSeek 环境文件、`--no-access-log`、以 `sima-draft` 用户运行，并通过 `/health` 回读。
- [x] Nginx 加入精确的 `/weiquan/api/consumer`、`/weiquan/api/business` 同源 POST 代理和 `/weiquan/` 明确静态映射；API location `access_log off`、`no-store`、`no-cache`；`nginx -t` 通过后 reload。
- [x] 原子更新门户首页，新增 `/weiquan/` 卡片；公网回读首页、三页面、未知路径 404、两条短文本 400 及缓存头。
- [ ] **Release Blocker：** 两端成功、两端限流和两端 400 的缓存头已回读；Provider 异常缓存头、生产日志与第三方处理审计、浏览器 E2E、移动端和完整 Model 回归尚未补齐；不得声明 MVP COMPLETE。

### 生产浏览器与响应式回读（2026-08-24）

- [x] Chrome 实测角色页、消费者页、经营者页在 320、375、390、430、768、1440px 均无页面级横向滚动；标题、输入区和操作按钮存在。
- [x] 消费者端短文本不会发起 AI 请求，点击后显示输入校验文字；页面控制台未发现 error。
- [ ] **Release Blocker：** 成功态长函件、Copy、Reset、429、502、503、超时和 Provider 完整 Contract 仍须以虚构脱敏文本、经明确模型额度授权后回读。

### 生产真实 Provider 与 E2E 最小验收（2026-08-24）

- [x] 在明确额度授权下，以虚构脱敏文本完成消费者与经营者真实 DeepSeek 请求；两端均通过前端严格 Contract 校验并渲染完整固定结果区，控制台无 error。
- [x] 两端 Copy 显示文字成功反馈；Reset 后输入、结果和 checklist 均回到初始状态。
- [x] 修复前端 55 秒 Abort 早于服务端 60 秒 Provider 上限的时序缺陷：前端改为 70 秒、两条 Nginx API 代理改为 75 秒；语法检查与 reload 后成功态回读通过。
- [ ] **Release Blocker：** 429、502、503、500、超时的生产状态与 Header、成功态长函件移动端、Provider 留存书面边界、完整对抗矩阵和发布日法律复核仍未完成。

### Consumer Contract 修复与移动端回读（2026-08-24）

- [x] 修复消费者数组元素校验：每个元素必须是非空字符串且不超过 Schema 规定长度；新增 `None`、空白和超长元素回归，28 项相关离线测试通过。
- [x] 已对生产单文件创建回滚副本、原子替换并重启服务；`/health` 回读通过。
- [x] 320px 真实请求的 Provider unavailable 回退无横向溢出、console 无 error。
- [ ] **Release Blocker：** 该移动端请求未形成成功态，长函件移动端仍未通过；Provider 间歇不可用原因需在不记录正文的前提下另行观测与处理。

### Provider 脱敏可观测性（2026-08-24）

- [x] Provider 失败仅记录 endpoint、HTTP 状态、耗时和异常类型；单元测试确认虚构案件正文不会进入该日志。
- [x] 生产单文件已备份、部署、重启；健康检查与公网短文本 400/no-store 回读通过。
- [ ] **TBD：** 需等待后续真实请求的无正文诊断元数据，才能判断间歇不可用属于超时、上游状态或其他异常；不得通过压测或记录正文来制造证据。

### 生产限流与 Telemetry 回读（2026-08-24）

- [x] 以 21 个无效短文本请求分别验证消费者与经营者全局限流；两端第 21 个请求返回 429，并回读 `no-store` / `no-cache`。未调用 Provider。
- [x] 静态页面扫描未发现第三方 Analytics、Sentry、PostHog、Hotjar、Clarity、Datadog 或 New Relic；服务以 `--no-access-log` 运行，Nginx 两条精确 API location 均为 `access_log off`。
- [ ] **TBD：** 无法仅由本站静态与服务配置确认 CDN、宿主机或 Provider 的保留策略；页面和隐私文案不得作绝对不留存承诺。

### 第三方处理边界披露（2026-08-24）

- [x] 核验 DeepSeek 官网现行隐私政策：适用于 API，且未承诺零留存；开放平台条款要求下游应用运营者披露处理规则。
- [x] 三页页脚改为仅承诺本站不建立案件档案或长期保存用户输入，并披露处理内容会发送至 AI 服务提供方、以其适用政策为准。
- [x] 生产已先备份至 `/opt/backups/weiquan-privacy-footer-20260824-1439`，再逐页同步；本地/生产 SHA-256 一一对应，公网三页均回读新文案和各自页面内容。
- [x] 消费维权专项全量本机回归重新执行：29 项通过；`git diff --check` 通过。

### L-008 官方页面直读复核（2026-08-24）

- [x] 原最高人民法院公报 L-008 固定 URL 在当前网络路径返回 HTTP 502；已改用最高人民法院官网可直读的发布及全文页（`https://www.court.gov.cn/zixun/xiangqing/459321.html`）完成复核。
- [x] 确认法释〔2025〕4号、2025-05-01 施行及生活消费领域预付式消费适用范围；维持既有受控范围，不新增具体条文号或推断。

### 发布日法律来源复核（2026-08-24）

- [x] L-001 至 L-009 的名称、效力层级、发布/施行信息和允许引用主题再次按官方来源复核；未新增或扩张模型可展示条文号。
- [x] L-004 改用全国人大法律法规数据库官方全文，替换当前抓取端不可读的原公报 PDF。
- [x] L-008 已以最高人民法院官网发布及全文页直读复核；法律来源门禁不再以该项阻塞发布。
