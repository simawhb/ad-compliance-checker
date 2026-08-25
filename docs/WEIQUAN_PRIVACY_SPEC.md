# 消费维权助手隐私数据流基线

更新：2026-08-21（Asia/Shanghai）
阶段：消费者与经营者 API 本机实现；生产运行时与部署仍是待核验事项。

## Stage 2 静态原型核验

- 本机 `portal/weiquan/` 的三张页面只运行静态 HTML/CSS/原生 JavaScript；未创建服务端接口或真实网络请求。
- textarea 内容、证据勾选、Mock 结果及复制反馈仅在当前页面运行时 DOM 中存在；刷新或关闭页面即丢失。
- 静态检索未发现 localStorage、sessionStorage、IndexedDB、Cookie、fetch、AI Provider 或案件历史实现。
- 本节仅覆盖本机原型；生产 `/weiquan/` 尚未部署，既有 Nginx、日志、缓存和 Provider 边界仍按下文 Release Blockers 处理。

## 候选实现的已验证数据流

| 节点 | 已验证行为 | 持久化/日志 | 风险判断 |
|---|---|---|---|
| 浏览器广告审查页 | 文本经 `fetch` 同源提交；localStorage 仅存非正文历史标签。 | 无广告正文持久化已由代码确认。 | 消费维权不可沿用历史记录逻辑。 |
| FastAPI 主工程 | 接收 JSON 文本；可选内存结果留存默认关闭。另含上传、OCR、URL 抓取、PDF 路径。 | 上传临时文件最长可留 24 小时；结果留存可由环境变量开启。 | 不得复用作消费维权接口。 |
| 独立起草服务 | 接收纯文字 JSON，返回 JSON；为首页和 `/api/draft` 设置 `no-store`。 | 代码未见结果数据库。生产错误日志配置未确认。 | 可作为最小纯文本服务参考，不等同于已批准复用。 |
| AI Provider | 服务端以环境变量密钥向 DeepSeek 兼容 API 发出 Prompt。 | 用户文本会发送给 Provider；DeepSeek 现行隐私政策明确覆盖 API，并说明信息可能按提供服务、合规、改进与安全等目的留存。 | 第三方处理，页面不得宣称 Provider 不留存；以其适用政策为准。 |
| 生产反向代理 | 生产 Nginx 使用根门户回退路由；可见全局 access/error log，另有部分服务专用日志。 | 消费维权路由尚不存在，无法确认未来 API 的日志格式、正文和缓存行为。 | Release Blocker。 |

## 已检查结果

- 本机候选前端未发现 sessionStorage、IndexedDB 或 Cookies 用于广告文本。
- 本机候选前端和线上门户 HTML 未发现 Analytics、Sentry、PostHog、Hotjar、Clarity 等明显第三方脚本引用。
- 当前 Nginx 显示全局访问/错误日志；不读取日志正文，故无法确认未来请求会记录哪些字段。CDN、运行时注入脚本和错误监控仍为 TBD。
- 候选主工程的抓取/OCR日志和临时上传不符合消费维权 MVP 的“文字描述 + 模板生成”范围。

## 消费维权 Release Blockers

在以下事项经代码和生产配置共同核验前，不得声明“不保存用户内容”或进入发布审查：

1. 不存在 localStorage、sessionStorage、IndexedDB、Cookie、案件数据库、文件上传或历史记录对案件正文的保存。
2. 接口、异常处理、访问日志、错误监控、Analytics、CDN/代理缓存不记录完整纠纷正文或完整 Prompt。
3. AI Provider 的发送范围、保留边界和页面说明一致。
4. 所有纠纷接口为文字 JSON，具备 `Cache-Control: no-store`，并不暴露 OCR、上传、URL 抓取或 PDF/结果查询路径。
5. 生产 Nginx、应用进程和部署目录实际可读验证，而非仅引用模板。

## 已冻结的消费维权数据生命周期

```text
1. 用户在浏览器 textarea 输入（仅当前页面内存）
2. 用户主动提交
3. POST request body 发送至同源 /weiquan/api/{consumer|business}
4. 专用纯文字服务仅为当前请求处理
5. 服务端以环境变量中的 DeepSeek Key 调用 Provider
6. Provider 响应经服务端 schema 校验
7. 服务端以 no-store 响应返回浏览器
8. 浏览器即时渲染；不写 localStorage、sessionStorage、IndexedDB 或案件历史
9. 页面关闭或刷新后，前端案件正文不再由本工具保留
```

本站主动案件持久化：**NONE**。

基础设施元数据与案件内容不同：当前 Nginx access/error log 可能保存 URL、时间、状态等；因此正文绝不进入 URL，应用错误处理不得 dump request body、Prompt 或模型完整响应。AI Provider 是必要第三方处理节点，其数据处理边界须在后续法律/隐私审查中按实际条款披露，不能写成“绝不存储任何数据”。

## 已冻结日志与缓存策略

- 可记录：时间、endpoint、HTTP status、延迟、随机 request ID、Provider error code。
- 禁止记录：request body、纠纷正文、完整 Prompt、完整 AI Response、协商函、回复函、身份或案件标识。
- Case Content 响应：`Cache-Control: no-store`、`Pragma: no-cache`；禁止代理缓存。
- Static Asset：可沿用门户静态资源缓存策略，但不得携带案件内容。

## 消费者与经营者端代码核验（未部署）

| 节点 | 当前代码行为 | 主动持久化/日志 |
|---|---|---|
| `portal/weiquan/assets/weiquan.js` | 同源 `POST /weiquan/api/{consumer|business}`，request body 仅 `{text}`；55 秒浏览器超时后丢弃引用。 | 无 localStorage、sessionStorage、IndexedDB、Cookie、URL 正文或历史存储。 |
| `backend/weiquan_consumer_service.py` | 仅为单次请求构造消费者或经营者服务对象；全局限流队列仅存单调时间戳，不存 IP、身份或文本。 | 错误日志仅记录异常类别；不记录 request body、Prompt、模型原始输出或函件。 |
| `backend/weiquan_consumer.py` | 进程内临时组合 Prompt、调用 Provider、严格校验并返回结构化结果。 | 无文件、数据库、缓存或历史实现。 |
| DeepSeek Provider | 由已有服务端 `backend/llm.py` 使用环境变量 Key 调用。共享客户端的异常与解析失败日志已改为只记录异常类型/固定消息，不记录 Provider 异常文本或模型文本片段。 | 仍属第三方数据处理；2026-08-24 已核验其官网现行隐私政策覆盖 API，且并不承诺零留存。 |

`/api/consumer` 与 `/api/business` 的所有成功和错误 HTTP 响应设计为 `Cache-Control: no-store`、`Pragma: no-cache`；已在项目 `.venv` 的 Fake Provider HTTP smoke 中核验成功、400、502 与 503 响应，并以本机 Uvicorn 回读两条接口的成功响应 `no-store` Header；不会向真实 Provider 发送测试正文。部署前仍须在受控环境复核实际代理 Header 与错误处理。

## 本机隐私安全专项审计（2026-08-24）

- 消费维权前端、两端核心与服务外壳的静态检索未发现案件正文持久化、Cookie、浏览器 Analytics/错误监控脚本或第三方案件传输；经营者端唯一外链仍为既有广告审查工具。
- 共享 `LLMClient` 曾记录 Provider 异常文本及解析失败的模型文本片段。该路径虽不由消费维权的严格 JSON 解析调用，但为防未来复用或异常绕行，已统一改为仅记录异常类型或固定消息，并以合成字符串回归测试验证不写入日志。
- 本机代码结论不覆盖 CDN 或宿主机层的独立留存策略。生产 Nginx、服务与 DeepSeek 的第三方处理边界已按各自可得证据核验；本站页面必须仅承诺本站不建立案件档案或长期保存用户输入，不承诺第三方零留存。
