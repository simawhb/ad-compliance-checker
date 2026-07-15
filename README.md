# 驷马合规 · 电商页面广告审查系统

## 功能概述

电商产品页面链接直接输入 → 系统自动读取页面内容 → 完成广告宣传合规审查，对标市场监管执法检查深度。

### 双通道方案

| 通道 | 方式 | 适用平台 |
|------|------|---------|
| **方案A** | Playwright 自动抓取 | 独立站/企业官网、京东 |
| **方案B** | 截图上传 + OCR | 淘宝/天猫、拼多多、抖音小店（反爬严重） |

### 审查维度

标题审查、价格审查、功效宣称、数据来源、资质展示、对比广告、极限词审查

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

2. **启动服务**
   ```
   cd backend
   python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

3. **打开前端**
   浏览器访问 `http://127.0.0.1:8000`

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/check-page` | URL 自动抓取审查 |
| POST | `/api/check-page/upload` | 截图上传审查 |
| POST | `/api/ocr/preview` | OCR 预览（可修正） |
| GET  | `/api/result/{id}` | 获取审查结果 |
| GET  | `/api/result/{id}/pdf` | 下载 PDF 报告 |
| GET  | `/api/health` | 健康检查 |

## 技术栈

- **框架**: FastAPI + Uvicorn
- **页面抓取**: Playwright (Chromium headless)
- **OCR 识别**: PaddleOCR (GPU) + easyocr (fallback)
- **合规审查**: DeepSeek V4 Pro (LLM)
- **报告生成**: ReportLab (PDF)
- **GPU 加速**: GTX1060 (CUDA 11.x)
