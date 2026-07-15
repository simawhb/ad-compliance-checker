# 广告审查助手 · 力邦营养企业定制版

**北京华象（西安）律师事务所** 为 **力邦营养** 定制的企业内用广告合规审查工具。

## 快速启动

### 环境要求
- Windows 10+ / Windows Server 2016+
- Python 3.9+

### 启动步骤

```bash
# 1. 安装依赖
pip install -r backend\requirements.txt
pip install aiofiles jinja2

# 2. 启动服务
python start_server.py
```

浏览器访问 **http://127.0.0.1:8000**

### 一键启动
双击 `start_libang.bat` 即可。

---

## 功能说明

| 功能 | 说明 |
|------|------|
| **快速检测** | 基于规则引擎和违禁词库，秒级出检测结果 |
| **AI 深度分析** | 调用大模型进行语义合规审查（需配置 API Key） |
| **批量审查** | 支持多文案批量检测与对比 |
| **图片识别** | 上传图片自动 OCR 识别文字 |
| **报告导出** | 检测结果一键导出 PDF 报告 |

## 行业覆盖

**深度覆盖：** 特殊医学用途配方食品、普通食品  
**同时保留：** 化妆品、医疗、教育、金融、房地产等通用行业

## 配置 API Key（可选）

创建 `.env` 文件：

```
DEEPSEEK_API_KEY=sk-your-key-here
```

不配置不影响快速检测，仅 AI 深度分析不可用。

## 目录结构

```
ad-checker-libang/
├── start_server.py          # 启动入口
├── start_libang.bat         # Windows 一键启动
├── requirements.txt         # Python 依赖
├── backend/                 # 后端 API
│   ├── main.py              # FastAPI 主程序
│   ├── detector.py          # 检测引擎
│   ├── llm.py               # AI 分析模块
│   └── user.py              # 用户管理
├── frontend/                # PC 桌面端
├── h5/                      # 手机端
├── batch/                   # 批量审查
├── knowledge/               # 违规词库
├── data/                    # 数据库
├── docs/                    # 文档
└── configs/                 # 服务端配置参考
```

## 常见问题

**Q: 启动后页面空白？**  
检查 Python 依赖是否安装完整。首次运行会自动创建数据库。

**Q: 端口 8000 被占用？**  
修改 `start_server.py` 中的 `port=8000` 为其他端口（如 8001）。

**Q: 需要外网访问？**  
参考 `configs/` 目录下的 Nginx 配置示例。

---

*力邦营养企业定制版 · 广告审查助手 — 内部合规自查使用*
