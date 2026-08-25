# 驷马合规·广告审查助手 — 部署说明

## 文件说明

从服务器下载的两个文件：

| 文件 | 用途 |
|------|------|
| `ad-compliance-checker.tar.gz` | 项目全部代码（后端 + 前端 + 知识库） |
| `server-configs.tar.gz` | 服务器配置文件（nginx / systemd / .env） |

---

## 一、解压项目

```bash
# Windows 推荐用 7-Zip 或 tar 命令解压
tar -xzf D:\驷马仓库\ad-compliance-checker.tar.gz -C D:\驷马仓库\

# 解压后项目路径
D:\驷马仓库\ad-compliance-checker\
```

---

## 二、安装依赖

```bash
cd D:\驷马仓库\ad-compliance-checker

# 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate

# 安装 Python 依赖
pip install -r backend\requirements.txt
pip install aiofiles jinja2
```

---

## 三、配置 API Key

创建 `.env` 文件（从 server-configs.tar.gz 中提取）：

```bash
# 解压配置参考
tar -xzf D:\驷马仓库\server-configs.tar.gz -O > D:\驷马仓库\ad-compliance-checker\.env
```

或手动创建 `D:\驷马仓库\ad-compliance-checker\.env`：

```
DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY
```

---

## 四、启动服务

```bash
cd D:\驷马仓库\ad-compliance-checker
python start_server.py
```

启动后访问：**http://127.0.0.1:8000**

---

## 五、部署到主力机（如需要外网访问）

### 方案 A：本地使用（推荐）
服务默认监听 `0.0.0.0:8000`，本机浏览器访问即可。
局域网内其他设备用 `http://你本机IP:8000` 访问。

### 方案 B：配置 Nginx 反向代理（参考服务器配置）

```bash
# server-configs.tar.gz 中包含的 nginx 配置文件参考
# 路径：/etc/nginx/sites-available/ad-checker
```

### 方案 C：HTTPS 证书
主力机如需要 HTTPS，参考服务器配置安装 Let's Encrypt：

```bash
certbot --nginx --agree-tos --email wanghgbg@outlook.com -d 你的域名
```

---

## 六、开机自启（Windows）

创建 `start.bat`（已包含在项目中）：
```bat
@echo off
cd /d D:\驷马仓库\ad-compliance-checker
call venv\Scripts\activate
python start_server.py
pause
```

添加到开机启动：
1. Win+R → `shell:startup`
2. 将 `start.bat` 的快捷方式放进去

---

## 七、目录结构

```
D:\驷马仓库\ad-compliance-checker\
├── start_server.py          # 启动入口
├── backend/
│   ├── main.py              # FastAPI 主程序
│   ├── detector.py          # 检测引擎
│   ├── llm.py               # AI 分析
│   ├── user.py              # 用户管理
│   ├── pdf_report.py        # PDF 报告
│   └── admin/               # 管理后台
│       ├── index.html
│       └── login.html
├── frontend/                # PC 前端
├── h5/                      # 移动端
├── knowledge/               # 知识库（违规词库等）
├── docs/                    # 文档
├── index.html               # 首页
└── .env                     # API Key 配置（需自行创建）
```

---

## 八、常见问题

**Q: 端口 8000 被占用？**
修改 `start_server.py` 中的 `port=8000` 为其他端口。

**Q: 启动后页面空白？**
检查 `.env` 中 API Key 是否正确配置。

**Q: 知识库文件在哪里？**
`knowledge/forbidden_words.json`，包含 500+ 违规词库和多行业规则。

**Q: 数据库在哪？**
`backend/users.db`（SQLite），首次启动自动创建。
