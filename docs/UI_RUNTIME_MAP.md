# UI 与运行时映射：消费维权助手 Stage 4（本机未部署）

更新：2026-08-21（Asia/Shanghai）

## 线上门户

| URL | 实际响应 | 用途/结论 |
|---|---|---|
| `https://4ma.wang/` | `/var/www/4ma.wang/index.html`，静态 HTML，HTTP 200 | 工具门户：首页含导航、工具卡、更新日志和统一页脚；公网与生产文件 SHA-256 一致。|
| `https://4ma.wang/weiquan/` | 与首页相同静态 HTML，HTTP 200 | 当前为回退响应；不是消费维权页面。|
| `https://checker.4ma.wang` | 首页卡片指向 | 现有广告宣传审查助手入口。|
| `https://draft.4ma.wang/` | 独立 FastAPI 服务 | 现有广告宣传合规起草助手；健康接口已只读确认。|

## 本机候选页面与路由

| 本机组件 | 页面/API | 说明 |
|---|---|---|
| `backend/main.py` | `/`、`/h5/`、`/privacy`、`/terms`、`/api/check`、`/api/draft` 等 | 广告审查主工程，含实验性上传和 OCR，不适合直接暴露给消费维权 MVP。|
| `backend/draft_service.py` | `/`、`/api/health`、`/api/draft` | 纯文本广告起草独立服务，具备 no-store 中间件和同源调用模式。|
| `frontend/index.html` | 广告审查主页面 | 原生 JavaScript，文本输入、结果、复制、隐私/条款链接、移动端样式。|
| `frontend/draft.html` | 广告起草页 | 纯文字输入及服务端 JSON 提交参考。|
| `frontend/privacy.html`、`terms.html` | 隐私、使用规则 | 现有独立说明页参考；消费维权须另行按真实实现编写声明。|

## 设计系统（已观察）

- 页面：静态 HTML + 内嵌 CSS + 原生 JavaScript；不依赖 React、Vue、Tailwind 或状态管理库。
- 视觉：深色底、半透明蓝灰卡片、圆角、紧凑按钮、中文优先排版。
- 响应式：以 CSS media query 将双列输入网格切换为单列；现有页面为同一 HTML 兼容 `/` 与 `/h5/`。
- 可复用交互：必填校验、禁用提交按钮、文本状态提示、Clipboard 复制、隐私/条款链接。

## 运行时与隐私边界

```text
候选消费维权页面（尚未实现）
  -> 同源 /weiquan API（尚未实现）
  -> 服务端受控 AI Provider 调用
  -> 仅在当前页面显示结构化响应
```

必须避免的现有能力：文件上传、OCR、URL 抓取、PDF 输出、结果查询、可选内存结果留存及前端历史记录。

## 已验证的广告助手调用链

```text
广告审查浏览器页
  -> fetch('/api/check' 或 '/api/draft')
  -> FastAPI: backend/main.py 或 backend/draft_service.py
  -> backend/llm.py 读取服务端 DEEPSEEK_* 环境变量
  -> httpx POST 到 DeepSeek 兼容 Chat Completions URL
  -> 文字 JSON/模型文本返回 FastAPI
  -> 前端原生 JavaScript 渲染、复制及（广告页）非正文历史标签
```

广告审查模型输出是提示 JSON 后的服务端解析，不是 Provider Schema 强约束；消费维权后续需采用独立、受检验的结构化响应契约。

## 阻断映射

已确认 `enterprise-trial-rollout/portal/index.html` 是当前门户的受控源码基线：与生产首页仅差一条 2026-08-15 更新日志，卡片与链接数量一致。旧版 `libang-custom/4ma_wang_portal*.html` 不再作为门户修改来源。生产根路径会以 `try_files` 回退至 `/index.html`，并且生产目录尚不存在 `weiquan/`。

因此，首页工具卡、门户导航和页脚应从该受控基线复用；已完成上述一行生产变更同步。`/weiquan/` 子路径尚未实现，已在 Stage 1 冻结其静态部署映射与 IA。

## 消费维权本机静态原型映射（Stage 2 已实现，未部署）

```text
/weiquan/                    -> portal/weiquan/index.html -> assets/weiquan.css -> 无 API -> 共享静态 Header/Footer
/weiquan/consumer/           -> portal/weiquan/consumer/index.html -> ../assets/weiquan.css + ../assets/weiquan.js -> same-origin POST /weiquan/api/consumer -> 当前 DOM
/weiquan/business/           -> portal/weiquan/business/index.html -> ../assets/weiquan.css + ../assets/weiquan.js -> same-origin POST /weiquan/api/business -> 当前 DOM
/weiquan/api/consumer (POST) -> dedicated text-only service /api/consumer -> backend/weiquan_consumer_service.py -> backend/weiquan_consumer.py -> backend/llm.py -> DeepSeek
/weiquan/api/business (POST) -> dedicated text-only service /api/business
```

消费者与经营者页面都只发送 `{text}` 的 POST JSON body，不在 URL、Cookie、Storage 或页面历史中放入案件正文；临时本机同源服务已以 Fake Provider 回读两条 API 的 Contract 与 `no-store`，但 API 接线后的浏览器端到端交互尚待有可用浏览器实例时复验。现有 `location /api/` 已归属良选服务，故未来不得占用根 `/api/weiquan/*`。两个 API 采用精确 Nginx location；`location ^~ /weiquan/` 使用 `try_files $uri $uri/ =404`，使不存在的消费维权子路径明确 404，不回退门户首页。
