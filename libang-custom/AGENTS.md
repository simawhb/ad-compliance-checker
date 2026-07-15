# 驷马合规·广告审查助手

## 项目概述

AI 广告文案合规检测工具。输入广告文案，输出合规评分、风险高亮、修改建议和关联法条。

## 项目结构

```
ad-compliance-checker/
├── backend/                 # FastAPI 后端
│   └── requirements.txt     # 依赖：fastapi, uvicorn, pydantic, pytesseract, Pillow
├── miniprogram/             # 微信小程序前端
│   └── pages/
│       ├── index/           # 首页（输入检测）
│       ├── result/          # 检测结果页
│       └── upgrade/         # 升级页面
├── docs/
│   ├── PRD.md               # 产品需求文档
│   ├── user-analysis.md     # 用户分析
│   └── deployment.md        # 部署文档
├── start.bat                # 启动脚本
├── .gitignore
└── AGENTS.md                # 本文件
```

## 技术栈

- **后端**：FastAPI (Python 3.x)
- **前端**：微信小程序（WXML/WXSS/JS）
- **部署**：本机部署，cpolar 公网隧道

## 部署信息

- **项目位置**：`D:\WorkBuddy\legal-ai\ad-compliance-checker\`
- **启动脚本**：`start.bat`
- **服务端口**：8000
- **开机自启**：计划任务 AdCheckerService
- **公网地址**：`https://2417e45a.r36.cpolar.top`
- **防火墙**：已开放端口 8000 (AdChecker)

## 启动方式

```bash
# 后端启动
cd D:\WorkBuddy\legal-ai\ad-compliance-checker
python -m uvicorn main:app --host 127.0.0.1 --port 8000

# 或直接运行
start.bat
```

## 功能规划

| 版本 | 价格 | 功能 |
|------|------|------|
| 免费 | 0 | 每日3次检测 |
| 个人 | 29.9/月 | 无限检测 |
| 专业 | 99/月 | 行业定制规则 |
| 企业 | 999/月起 | API接入 |

### MVP 功能（按优先级）
- **P0**：合规检测（评分 + 高亮 + 建议 + 法条）
- **P0**：违规词库（500+词条，分行业）
## 审查历史

### 2026-06-17 三轮审查

| 轮次 | 重点 | 修改内容 |
|------|------|---------|
| 1 | 代码规范 + 产品 | API 返回格式统一、PC端自动注册、替换建议扩展至 6 行业 128+ 条 |
| 2 | 功能补齐 | 批量检测、PDF 导出、easyocr 单例、管理统计、数据自动过期 |
| 3 | 数据隐私 + 安全 | 原文不存库（20字摘要）、30天自动清理、管理后台登录、平台差异规则 |

**安全红线（不可违反）：**
- 用户上传的广告文案原文不得明文存储（只能存 20 字摘要）
- 检测记录 30 天后自动删除
- 管理后台必须登录才能访问
- 错误信息不得暴露内部细节
- 所有 API 返回格式统一为 `{"ok": bool, "data": ...}`

详细审查清单见 `docs/review-checklist.md`

- **P1**：历史记录 + PDF报告
- **P2**：行业定制规则

## 关联 Agent

- **Lex**（合规顾问）：法律文书、广告合规审查 — 本项目核心对接 Agent
- **Nova**（内容策划）：三账号内容生产 — 审查结果可反哺内容

## 重要规则

1. **批处理脚本禁止中文**：.bat / .cmd 文件中的 echo、title、注释等全部使用英文。Windows cmd.exe 默认用 GBK 编码，UTF-8 中文会被解析为乱码命令导致报错。PowerShell (.ps1) 无此限制。
2. **Python 文件保持 UTF-8**：所有 .py 文件使用 `# -*- coding: utf-8 -*-` 头，中文注释/字符串正常。
3. **前端 HTML 用中文**：前端界面 h5/index.html 和 frontend/index.html 的中文文本正常使用，不受此规则限制。
4. **对外身份**：产品推广时写"北京华象（西安）律师事务所 王洪兵"，不得写"王洪兵律师"（身份是专家顾问，非职业律师）。

