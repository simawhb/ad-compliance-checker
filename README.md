# 驷马合规 · 广告宣传文字合规审查助手

## 功能概述

对用户主动提交的广告文字进行合规风险提示，支持单条和批量文字审查。

首版同时提供“合规起草”入口，仅支持医疗健康和电商促销。起草流程强制执行“生成待审稿 → 同规则内部审查 → 最多一次自动修订 → 再次审查”；中高风险未消除时明确拦截，不把文案包装成可直接发布版本。

每次起草返回由待审文案、客户确认事实、证明材料和实际规则上下文共同计算的版本校验码；任一依据变化都会产生新版本。网页可复制带版本状态的待审文案，或复制包含客户确认事实、缺失材料、未采用主张、规则编号和内部审查结论的完整起草包。

起草表单按行业收集关键事实：医疗健康收集监管类别、批准/注册/备案信息及批准文案；电商促销收集宣传价格、活动期限、适用范围、优惠条件及比较价格依据。服务端独立预检缺项并强制合并到待补材料，模型不能自行删除这些缺项。

审查建议设有确定性安全兜底：涉及疾病治疗、功效、绝对化、排名和价格比较主张时，不把风险词机械替换成另一项未经证明的宣传主张，而是要求删除并在补齐批准内容、证明材料或比较依据后重新起草。

默认隐私策略：网页最近记录只保存“单条/批量、风险等级和时间”，不保存广告原文；服务端不留存审查结果。文案仍会发送至配置的模型服务，客户提交前应先删除个人信息和商业秘密。

用户提交前必须确认《使用规则》和《隐私规则》。所有合规起草结果在页面、复制文案和完整起草包中保留“AI辅助生成”标识。

网页以高、中、低风险等级表达结果，不使用容易造成“已经合规”误解的数字评分；批量审查按其中最高风险定级。所有结果均明确标注“风险提示不等于合规确认”。

### 产品边界

- 审查广告标题、正文、口播稿、字幕稿等用户确认后的文字。
- 不审查图片、画面、版式、人物形象、示意图、前后对比或视频视觉内容。
- OCR、网页抓取和截图上传代码仅作内部实验，客户版本默认关闭，不构成产品能力承诺。

### 审查维度

标题审查、价格审查、功效宣称、数据来源、资质展示、对比广告、极限词审查。结果同时列出完成事实核验仍需补充的证明、资质或数据来源，防止把材料不足误判为已经合规。

## 项目结构

```
ad-compliance-checker/
├── backend/
│   ├── main.py                    # FastAPI 入口
│   ├── llm.py                     # LLM 电商审查引擎（Lex）
│   ├── ocr_engine.py              # OCR 引擎（PaddleOCR + easyocr 备用）
│   ├── page_fetcher.py            # 页面抓取引擎（Playwright）
│   ├── platform_adapters/
│   │   ├── base.py                # 适配器基类
│   │   ├── standalone.py          # 独立站适配器
│   │   ├── jd.py                  # 京东适配器
│   │   └── manual.py              # 手工上传适配器
│   ├── schemas.py                 # 数据模型
│   ├── pdf_report.py              # PDF 报告生成
│   ├── mailer.py                  # 邮件发送
│   └── utils/
│       └── image_utils.py         # 图片处理工具
├── frontend/
│   └── index.html                 # Web 前端页面
├── scripts/
│   └── start.bat                  # Windows 启动脚本
└── requirements.txt               # Python 依赖
```

## 快速启动

1. **安装依赖**
   ```
   pip install -r requirements.txt -i https://mirror.baidu.com/pypi/simple
   playwright install chromium
   ```

   OCR 依赖仅用于内部实验；客户文字审查版无需启用。

2. **启动服务**
   ```
   cd backend
   export AD_COMPLIANCE_RULES_DIR="/绝对路径/规则库/02_已核验规则"
   python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

   `AD_COMPLIANCE_RULES_DIR` 必须指向 Obsidian 规则库的“02_已核验规则”目录。未配置、目录不存在或没有匹配规则时，`/api/check` 明确返回“审查未完成”，不会输出低风险结论。

3. **打开前端**
   浏览器访问 `http://127.0.0.1:8000`

   客户网页只呈现产品能力，不展示服务器、本机、模型或规则库等内部部署状态。本机能力仅用于研发验证，并可作为后续“AI 深度”模式的备选实现。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/draft` | 医疗健康/电商促销合规起草并自动内部审查 |
| GET  | `/terms` | 使用规则 |
| GET  | `/privacy` | 隐私规则 |
| POST | `/api/check-page` | 内部实验接口，默认关闭 |
| POST | `/api/check-page/upload` | 内部实验接口，默认关闭 |
| POST | `/api/ocr/preview` | 内部实验接口，默认关闭 |
| GET  | `/api/result/{id}` | 获取审查结果；仅在 `STORE_REVIEW_RESULTS=true` 时开放 |
| GET  | `/api/result/{id}/pdf` | 下载 PDF 报告；仅在结果留存开启时开放 |
| GET  | `/api/health` | 健康检查 |
| GET  | `/api/readiness` | 审查能力就绪检查（规则库、模型配置、OCR） |

## 技术栈

- **框架**: FastAPI + Uvicorn
- **页面抓取**: Playwright (Chromium headless)
- **OCR 识别**: PaddleOCR (GPU) + easyocr (fallback)
- **合规审查**: DeepSeek V4 Pro (LLM)
- **报告生成**: ReportLab (PDF)
- **GPU 加速**: GTX1060 (CUDA 11.x)

## 本机验收

`tests/fixtures/acceptance_cases.json` 提供四个完全虚构、无个人信息的首批验收样例，覆盖医疗健康和电商促销。它们用于结构、材料预检和安全回归，不替代真实模型准确率验收。

在配置真实模型密钥前，可运行：

```
PYTHONPATH=backend .venv/bin/python -m unittest discover -s tests -v
```

正式上线前仍须使用 3–5 个经确认可用的脱敏业务样例，逐项核对输出文字、规则编号、依据、修改建议、待补材料和内部复审状态。
