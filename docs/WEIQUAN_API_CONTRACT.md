# 消费维权助手 API Contract

更新：2026-08-23（Asia/Shanghai）
状态：消费者与经营者 API 均已本机实现；以 Fake Provider HTTP 测试和虚构脱敏真实 Provider 最小评测验证，未部署。

## Endpoint

| 用途 | 方法与同源路径 | Request |
|---|---|---|
| 消费者分析 | `POST /weiquan/api/consumer` | `{ "text": "用户纠纷描述" }` |
| 经营者分析 | `POST /weiquan/api/business` | `{ "text": "投诉内容或纠纷描述" }` |

禁止 GET、URL query/path/hash 携带正文；禁止 `userId`、`accountId`、`caseId`、设备指纹、historyId、文件和跟踪标识。

## 成功响应

消费者：

```json
{
  "disputeType": "",
  "summary": "",
  "factsKnown": [],
  "factsMissing": [],
  "legalBasis": [],
  "recommendedPath": [],
  "evidenceNeeded": [],
  "specialNotes": [],
  "letter": "",
  "disclaimer": ""
}
```

经营者：

```json
{
  "disputeType": "",
  "summary": "",
  "factsKnown": [],
  "factsMissing": [],
  "consumerClaimBasis": [],
  "businessResponsePoints": [],
  "evidenceNeeded": [],
  "possibleAbnormalClaimFeatures": [],
  "complianceCheck": [],
  "recommendedPath": [],
  "replyLetter": "",
  "disclaimer": ""
}
```

Consumer response 必须满足 [`schemas/weiquan_consumer_response.schema.json`](../schemas/weiquan_consumer_response.schema.json) 的 v0.1 JSON Schema：required 字段、类型、最大长度和 `additionalProperties: false` 均强制执行。`legalBasis` 是以受控 Source ID（`[L-xxx]`）开头的字符串数组，保持 Stage 1 字段结构，不要求前端解析自由 Markdown。

Business response 必须满足 [`schemas/weiquan_business_response.schema.json`](../schemas/weiquan_business_response.schema.json) 的 v0.1 JSON Schema。`consumerClaimBasis` 同样只允许本次服务端注入的 `[L-xxx]` 来源；`possibleAbnormalClaimFeatures` 每项必须是“需进一步核实”的限定性表述。服务端拒绝包含“职业打假”“恶意投诉”“敲诈”“消费者无权投诉”“无需赔偿”“直接报警”等模型定性输出。

缺 required 字段、类型错误、空必填文字、未知字段、超长字段、非 JSON 或带 Markdown fence 的 Provider 输出均视为 Invalid AI Response；服务端不得把原始内容交给前端。`disclaimer` 必须强制为标准文本；仅在其余对象通过严格校验后可由服务端补入。

前端在渲染前还会复核两端必填字段、字符串/数组类型、未知字段和标准免责声明。该检查不替代服务端 Schema；它仅防止反向代理异常、部署版本漂移或意外响应使页面渲染不完整函件。前端发现不合格响应时，按 `502 Invalid AI Response` 显示服务不可用状态，不保留或展示正文。

## 错误与 HTTP 边界

| 类型 | HTTP | 安全响应原则 |
|---|---|---|
| Validation Error | 400 | 不回显完整正文。|
| Network / Timeout / Provider unavailable | 503 或 504 | 仅返回用户可理解的重试提示。|
| Invalid AI Response | 502 | 不返回 Provider 原始响应。|
| Server Error | 500 | 不返回内部异常、Prompt 或正文。|

错误响应仅返回通用 `{ "error": "…" }`；可在响应 Header 使用随机 `X-Request-ID` 用于最小技术诊断，且不得把它与身份或案件历史关联。

## 服务端与缓存边界

```text
Browser → same-origin POST → dedicated text-only service
→ DeepSeek server-side call → schema validation → same-origin response → Browser
```

两条业务响应都必须返回：

```http
Cache-Control: no-store
Pragma: no-cache
```

应用不创建案件数据库、文件、缓存或历史；不得记录 request body、完整 Prompt、AI 原始/完整 Response、协商函或回复函。

## Nginx 方案（设计，未部署）

```nginx
location = /weiquan/api/consumer {
    proxy_pass http://127.0.0.1:8014/api/consumer;
    proxy_no_cache 1;
    proxy_cache_bypass 1;
}

location = /weiquan/api/business {
    proxy_pass http://127.0.0.1:8014/api/business;
    proxy_no_cache 1;
    proxy_cache_bypass 1;
}

location ^~ /weiquan/ {
    root /var/www/4ma.wang;
    index index.html;
    try_files $uri $uri/ =404;
}
```

实现时还须在 API location 添加 no-store 响应头、受控限流、回环代理头和不含正文的错误处理。具体端口 `8014` 是拟议专用端口，须在后续实现/部署阶段确认资源和 systemd 方案后才可使用。
