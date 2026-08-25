# 消费维权助手架构决策

更新：2026-08-21（Asia/Shanghai）

## D-001 门户受控基线

采用 `enterprise-trial-rollout/portal/index.html` 作为 4ma.wang 门户受控基线。2026-08-15 的促销活动更新日志已从生产同步，哈希与生产首页一致。生产目录不是 Git 工作树，不作为开发源。

## D-002 三路由与静态目录

冻结静态目录映射：

```text
/var/www/4ma.wang/weiquan/index.html             -> /weiquan/
/var/www/4ma.wang/weiquan/consumer/index.html    -> /weiquan/consumer/
/var/www/4ma.wang/weiquan/business/index.html    -> /weiquan/business/
```

Stage 2 只创建本机页面；生产目录和 Nginx 不在该阶段变更。

## D-003 API 命名与同源边界

冻结为 `POST /weiquan/api/consumer` 和 `POST /weiquan/api/business`。不得使用根 `/api/weiquan/*`，因为当前生产 `location /api/` 已转发至良选服务。

浏览器只调用同源路径；AI Provider Key 保持在服务端环境文件。拟议实现为独立、纯文字服务（端口和 systemd 名称待 Stage 5/部署设计确认），不复用含 OCR、上传、PDF、历史或结果留存的广告审查主服务。

## D-004 结构化响应

后续服务端用 schema 校验并渲染固定 JSON 字段。不得让前端解析自由 Markdown，也不得复用广告助手的花括号/代码块 JSON 回退解析。

## D-005 数据与日志边界

本站案件持久化：**NONE**。请求只含 `text`，无身份、案件、设备或跟踪字段。应用日志不得主动记录请求正文、Prompt、完整模型响应或函件正文；Nginx 可保留 URL、时间和状态等基础设施元数据，但正文绝不进入 URL。

## D-006 缓存边界

两条业务 POST 响应必须设置 `Cache-Control: no-store` 和 `Pragma: no-cache`。静态 HTML/CSS/JS 可按门户现行静态策略缓存；不得缓存案件内容或 AI 输出。

## D-007 Nginx 路由策略

拟议生产配置须在现有根 fallback 之前/以更高优先级加入：两个精确 API location、一个 `/weiquan/` 静态 location。该静态 location 使用 `try_files $uri $uri/ =404`，使未知 `/weiquan/*` 返回 404，绝不回退门户首页。

## D-008 广告审查联动

经营者结果仅提供“检查广告宣传合规”链接，跳转 `https://checker.4ma.wang/`。不复制审查逻辑、规则或 Prompt。

## D-009 法律层责任边界

法律依据字段与生成文本分离。具体条文号仅可来自后续 `docs/WEIQUAN_LEGAL_SOURCES.md` 的人工核验来源；未核验时仅作低确定性主题表述。

## D-010 Stage 2 仅使用本地 Mock Fixture

`portal/weiquan/assets/weiquan.js` 仅提供虚构、无可识别个人信息的固定 UI fixture，用于验证字段排版和交互状态。Mock 标识在结果区可见；不得将其表述为 AI、法律结论或真实案件结果。该阶段不含 `fetch`、Provider、API 或持久化。

## D-011 共享静态资产

三个页面复用 `portal/weiquan/assets/weiquan.css`；消费者和经营者端复用 `portal/weiquan/assets/weiquan.js`，通过 `body[data-mode]` 选择各自 fixture 与结果字段。静态门户没有模板引擎，Header/Footer 保持同一文案和结构；不引入框架或新的组件体系。

## D-012 Consumer 法律来源与 Prompt Grounding

Stage 3 Consumer 仅使用 `docs/WEIQUAN_LEGAL_SOURCES.md` 中标记 `ALLOW` 的官方核验来源。未来服务端按案件主题注入小型 `CONTROLLED_LEGAL_FACTS` 片段和 Source ID；不使用模型记忆、大型 RAG、自动抓取或第三方转载作为核心法律依据。法规/程序变更须更新来源版本并重跑相关 Evaluation。

## D-013 Consumer Schema 与输入边界

保持 Stage 1 的十个 Consumer response 字段，正式 Schema 定义为 `schemas/weiquan_consumer_response.schema.json` v0.1。未来 API 输入为去空白后 12 至 6,000 个 Unicode 字符，超长/过短均拒绝，不静默截断。前端不解析自由 Markdown；服务端必须 parse、strict validate、normalize 后才返回安全 JSON。

## D-014 Consumer 服务端实施边界

消费者端新增 `backend/weiquan_consumer.py` 与独立 `backend/weiquan_consumer_service.py`，不接入广告审查主服务。核心以标准库实现，HTTP 层才依赖既有 FastAPI/Pydantic/HTTPX；这使 Contract 可在无依赖环境离线测试，同时保持部署时沿用项目的服务端 DeepSeek 调用方式。

服务端每次请求从受控 `L-xxx` 主题中按文本关键词选取最多五项注入 Prompt；Provider 只能返回完整 JSON。除唯一标准免责声明外，缺字段、未知字段、Markdown fence、超长或未被本次注入的 Source ID 一律以 502 拒绝，绝不回传原始模型内容。

HTTP 外壳使用全局、不含身份的时间戳限流和并发限制；日志仅允许异常类别。项目 `.venv` 已用 Fake Provider 完成 HTTP smoke，但此决策不等于生产已验证：Nginx/systemd/Provider 的真实运行和日志边界仍须后续受控验证。

## D-015 Schema 与服务端校验同源

2026-08-23 静态审查发现 `summary` 和多个数组的服务端长度/数量限制与发布 JSON Schema 不一致。已统一为 Schema v0.1 的 `1200`、数组 `12 × 500` 及 `legalBasis` `6 × 500`，并新增自动一致性测试。服务端仍可在 Schema 之外执行更严格的来源 ID 白名单，不得放宽 Schema 已冻结的字段或额外属性限制。

## D-016 Consumer Prompt 强制十字段输出

真实 Provider 的 v0.1 回归返回合法 JSON，却系统性漏掉三个必填数组。保持服务端严格拒绝，不增加脆弱的自由文本补齐；将 Prompt 升级为 v0.2，列出十键骨架并明确空数组也不得省略。该修复仅针对结构化输出稳定性，不改变法律判断范围或允许来源。

## D-017 Consumer 使用 Provider JSON Object Mode

v0.2 实测仍出现未闭合 JSON。Consumer Provider 因此调用已有服务端 `LLMClient` 的可选 `response_format={"type":"json_object"}`，不改变广告审查调用。此参数只能请求 JSON 对象，不能替代服务端 Schema、字段长度、来源白名单或免责声明校验；任何不合格输出仍拒绝。

## D-018 测试 HTTPX 隔离

既有 LLM 单测在导入时无条件向 `sys.modules` 写入最小 `httpx` stub，使同一进程后续 FastAPI/ASGI 测试错误引用 stub。仅在真实 `httpx` 缺失时才注入该 stub，既保持无依赖环境的既有测试意图，也避免污染 Consumer API 测试运行时。

## D-019 真实模型失败不自动重试

授权后的虚构 Consumer 评测证明 JSON Object Mode 能使多数场景满足严格 Contract，但 AI 客服场景仍出现结构无效及空输出。为避免重复向 Provider 发送纠纷文本、无界额度消耗和以重试掩盖可靠性问题，正式服务不做自动内容重试，不做 Markdown/字符串恢复，也不补造业务字段；该场景继续返回安全失败状态并阻断 Consumer Gate。

## D-020 Consumer 输出 Token 上限

C06 的元数据确认 `finish_reason=length`，故将 Consumer 专用 `max_tokens` 从 3200 调整为 8192。该值只影响服务端单次模型输出上限；输入仍限 6000 字符，服务端仍限制 JSON 字段长度，且不增加自动重试。调整须通过连续 C06 真实回归，否则恢复 BLOCKED。

两次连续 C06 调用均通过严格 Contract，故解除 Consumer API 的本机模型稳定性阻塞；生产发布仍独立受路由、日志、缓存、浏览器端到端和 Release Review 门禁约束。

## D-021 Business 双维 Contract

经营者端采用独立十二字段 Contract，不把消费者端简单反转。`possibleAbnormalClaimFeatures` 只接受“需进一步核实”的客观特征，核心与 Prompt 同时拒绝职业打假、恶意投诉、敲诈、无需赔偿等定性；`complianceCheck` 必须独立存在，防止模块沦为单向对抗工具。

## D-022 页面文案必须匹配实际调用边界

Stage 2 的“静态交互原型 / 不发送真实请求”仅适用于当时的 Mock 阶段。消费者和经营者正常页面现已改为同源 POST，因此移除该表述，改为事实、证据、程序与合规参考，并保留“自行核验事实和法律依据”的边界说明。隐藏开发 Mock fixture 不作为正式用户文案。

本次仅以临时 Fake Provider 完成本机同源 HTTP Contract 回读；自动化环境没有可用浏览器实例，故不能把 HTTP 回读表述为浏览器 E2E PASS，也不改变生产路由、日志、缓存和部署的 Release Blocker 状态。

## D-023 受控法律名称与修订状态必须回归测试

2026-08-23 官方复核发现代码的 L-007 将现行市场监管总局令第121号误写为“暂行办法”。该名称属于被注入模型的受控法律事实，已更正为《市场监督管理投诉举报处理办法》并添加单元测试，防止旧第20号令名称回流。L-006 同步登记 2020 年总局令第31号修订状态，并更新至总局法规库的现行文本。

此次变更未增加任何可向用户输出的具体条文号，也不改变既有不自动定性、协商优先或结果不承诺规则。

## D-024 模型异常文本不得进入应用日志

消费维权复用 `LLMClient`，而第三方异常文本或模型原始输出可能含有案件内容。即便当前消费维权严格 JSON 链不调用广告审查的宽松解析函数，仍不能依赖调用路径隔离。因此共享客户端的通用异常、解析失败和电商审查异常均不得记录 `exc` 或模型片段；改为固定消息或异常类型。对外错误同样不回显 Provider 异常文本。

## D-025 输出安全必须由服务端校验兜底

消费者和经营者 Prompt 都禁止伪造、销毁或隐匿证据、威胁/曝光施压、虚报损失与隐瞒违法事实，但 Prompt 服从不是安全控制。两端 `parse_and_validate` 在 JSON Contract 校验后检查明确不安全的操作型文本；命中即拒绝整份 Provider 输出，不做删除片段或自动改写。这样避免服务端替模型修补内容而误保留上下文风险。

## D-026 前端不渲染不合格结构化响应

服务端 Schema 是主控制，但前端也应在渲染前拒绝字段缺失、类型不符、额外字段或免责声明不一致的响应。该前端检查不做内容修复、字段默认或自由文本解析；只将其映射为统一的 Invalid AI Response 状态，从而避免版本漂移时把 `undefined` 或残缺函件呈现给用户。
# D-019：第三方 AI 数据处理必须显式披露（2026-08-24）

DeepSeek 现行官网隐私政策明确适用于 API，并说明其可能依适用政策处理和保留信息。消费维权页脚不得使用可被理解为覆盖第三方的“仅当前处理”或“绝不保存”承诺。三页统一改为：本站不建立案件档案或长期保存用户输入；处理内容会发送至 AI 服务提供方，第三方数据处理以其适用政策为准。

影响范围仅限三页页脚和隐私文档；不改变请求、日志、缓存、模型或本站的无案件持久化实现。
