# 消费维权助手发布审查清单

更新：2026-08-24（Asia/Shanghai）
当前状态：**已完成受控生产部署；RELEASE BLOCKED — 尚未补齐全部发布门禁。**

## 发布前不可跳过的证据

| Gate | 必须证据 | 当前状态 |
|---|---|---|
| 路由 | 生产 `/weiquan/`、`/weiquan/consumer/`、`/weiquan/business/` 各自返回正确页面；未知 `/weiquan/*` 为 404，不回退首页 | PASS — 2026-08-24 公网 HTTP 回读 |
| API 代理 | 生产精确 `POST /weiquan/api/consumer`、`POST /weiquan/api/business` 同源回环代理；Key 不在浏览器 | PASS — 127.0.0.1:8014 健康检查及两条公网 400 回读 |
| 缓存 | 两条 API 的生产成功、400、429、502、503、500 均回读 `Cache-Control: no-store`、`Pragma: no-cache` | PARTIAL — 两端成功 200、两条 400、消费者 429、经营者 429 已回读；502、503、500 待补 |
| 日志 | 实际 Nginx、服务进程、错误监控与 Analytics 证明不记录正文、Prompt、原始输出或函件 | PARTIAL — 精确 API 已 `access_log off`、Uvicorn 已 `--no-access-log`、静态页未发现第三方 telemetry；基础设施/Provider 边界待补 |
| Provider | DeepSeek 数据处理边界、模型配置和 Key 权限按实际生产环境核验；页面声明不超出事实 | PASS — Key 仅在服务端；官网现行隐私政策明确覆盖 API 且不承诺零留存，三页页脚已如实披露第三方处理边界 |
| 法律 | `WEIQUAN_LEGAL_SOURCES.md` 全部 ALLOW 条目在发布日再次官方复核；无过期/虚构条号 | PASS — v0.3 发布日官方复核完成；L-008 已以最高人民法院官网发布及全文页直读复核 |
| 消费者模型 | C01–C20 以虚构、脱敏文本形成完整 Model 回归记录；不保存原始内容 | BLOCKED — 仅最小摘要覆盖 |
| 经营者模型 | B01–B10 与 Prompt Injection 形成完整 Model 回归记录；不得定性职业打假或恶意投诉 | BLOCKED — 仅最小摘要覆盖 |
| 浏览器 E2E | 同源 API 接线后的成功、400、429、502、503、超时、Copy、Reset、外链与控制台检查 | PARTIAL — 两端真实成功态、Copy、Reset、短文本校验和控制台检查通过；错误/限流/超时待补 |
| 响应式 | 320、375、390、430、768、Desktop 的页面无横向滚动；中文输入、长函件可用 | PARTIAL — 生产三页在六个宽度均无页面级横向滚动；320px 真实请求已验证错误回退，成功态长函件待补 |
| 安全 | 无上传、账号、案件历史、数据库、Cookie/Storage 正文；错误不回显内部信息 | 本机 PASS；生产 BLOCKED |
| 工程质量 | 全部项目命令、静态门禁、部署前 `git diff --check`、生产回读和回滚方案 | 本机部分 PASS；生产 BLOCKED |

2026-08-24 已按授权完成最小生产部署：备份位于生产主机 `/opt/backups/weiquan-20260824-124813`；静态目录、同源 API、低权限 systemd 服务和 Nginx 精确 location 已落地。Nginx 配置已通过 `nginx -t` 并 reload；服务以 `sima-draft` 账户运行，`/health` 返回 200。公网已回读首页卡片、三条页面、未知路径 404、两条 API 的短文本 400 与 `no-store`/`no-cache` 响应头。此记录不等同于全部 Release Gate 已通过。

同日生产 Chrome 浏览器回读：角色页、消费者页、经营者页在 320、375、390、430、768、1440px 均无页面级横向滚动；消费者页短文本点击“开始分析”展示输入校验文字，控制台 error 数为 0。经额度授权，以虚构脱敏文本完成消费者与经营者真实成功态；消费者展示十个固定结果区与“复制协商函”，经营者展示十二个固定结果区、异常特征“仅供进一步核实”说明与“复制回复函”。两端 Copy 均给出文字反馈，Reset 后 textarea、结果和 checklist 均清空，控制台 error 数为 0。

本次浏览器验收发现前端 55 秒 Abort 早于服务端 60 秒 Provider 超时。已将消费维权前端等待上限调整为 70 秒，并将两条 Nginx API 代理 read/send timeout 调整为 75 秒；Nginx 已再次通过语法检查并 reload。修复后两端真实成功态通过。

后续 320px 真实请求触发 Provider unavailable 回退，页面无横向溢出且 console 无 error；该现象不得写作成功态移动端证据。另发现消费者端数组元素校验被误置于不可达代码，已补回非空字符串/长度校验、增加回归测试并部署至生产；服务健康检查通过。该修复不涉及 Prompt、法律来源或持久化边界。

为区分 Provider 间歇不可用原因，服务端已新增仅含 `endpoint`、`status`、`latency_ms`、异常类型的失败诊断日志；禁止记录 request body、Prompt、模型响应或异常原文。该单文件更新已备份、部署、重启并通过健康检查与公网短文本 400/no-store 回读。

生产消费者成功响应的脱敏公网回读：HTTP 200、`Content-Type: application/json`、`Cache-Control: no-store`、`Pragma: no-cache` 均存在；仅检查十个顶级字段形状、数组字段类型和必填文本字段，临时响应文件已在检查后删除，未记录或展示正文。

生产经营者成功响应的脱敏公网回读：HTTP 200、`Content-Type: application/json`、`Cache-Control: no-store`、`Pragma: no-cache` 均存在。该次流式字段检查在本地解析引号错误后未消费响应正文，因此不以此作为新的字段形状证据；经营者字段 Contract 仍以此前浏览器真实成功态与离线严格 Schema 回归为准。

DeepSeek 当前官网隐私政策明确将 API 纳入适用范围，并未作零留存承诺；开放平台条款要求下游应用运营者向终端用户披露个人信息处理规则。三页页脚因此仅承诺本站不建立案件档案或长期保存用户输入，并明确处理内容会发送至 AI 服务提供方、第三方数据处理以其适用政策为准。该项已完成备份、逐页哈希核对及公网回读，Provider Gate 记为 PASS。

生产限流回读：消费者和经营者端均以连续 21 个无效短文本 POST 验证，第 21 个请求均返回 429，并包含 `Cache-Control: no-store` 与 `Pragma: no-cache`；该检查未调用 Provider，也未使用个人信息。生产静态资源未发现 Analytics、Sentry、PostHog、Hotjar、Clarity、Datadog 或 New Relic；服务环境变量仅含 DeepSeek Key、规则目录、CORS 和现有结果存储开关名称。此静态/服务配置证据不等同于 CDN、宿主机或 Provider 侧“绝不留存”的承诺。

## 本机已通过的可复核项

- 严格 Consumer / Business Schema、受控来源、免责声明、`no-store`、无状态限流和同源 POST 边界。
- Provider 异常/模型文本不进入应用日志；输出安全兜底拒绝伪造、销毁/隐匿证据、隐瞒违法事实、曝光施压和虚报损失。
- 静态页、响应式/可访问性基础、无浏览器案件存储、前端不渲染不合格响应。
- 29 项消费维权专项本机测试通过（2026-08-24）；此数字必须在发布前重新执行并记录实际结果。

## 发布操作前的授权边界

以下均需单独明确授权：生产 Nginx 修改、静态文件同步、systemd/service 创建或重启、环境变量变更、真实生产 Provider 调用、公开发布。

部署时必须先准备：备份目标、验证命令、回滚命令、资源评估与最小变更清单。不得在生产主机运行高内存前端构建。

## 最终结论格式

仅当上表所有 Gate 都有对应生产证据时，才允许写：

> 消费维权助手 MVP COMPLETE

任一 Gate 未完成时，只能写：

> RELEASE BLOCKED

并列明缺失证据、影响和下一步授权需求。
