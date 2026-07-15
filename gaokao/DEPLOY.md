# 驷马报考 - 部署指南

## 当前状态

| 项目 | 状态 |
|------|------|
| 数据库 | 100,334 条录取数据，2,952 所院校 |
| API 服务 | FastAPI，端口 8000 |
| AI 问答 | DeepSeek API（.env 配置） |
| 前端 | Vue3 单页，已适配所有 API 字段 |
| 数据管线 | 每日 03:00 自动巡检 |

## 一、本地开发环境

```bash
cd D:\WorkBuddy\gaokao-database

# 安装依赖
python -m pip install fastapi uvicorn python-dotenv requests

# 配置 .env
cp .env.example .env  # 如果没有
# 编辑 .env 填入 DEEPSEEK_API_KEY=sk-xxx

# 启动服务
python src/api/app.py
# 访问 http://127.0.0.1:8000
```

## 二、生产环境部署（推荐方案）

### 方案 A：阿里云轻量应用服务器（推荐）

#### 1. 服务器配置
- **规格**: 2核4G，50G SSD
- **系统**: Ubuntu 22.04 LTS
- **带宽**: 5Mbps
- **费用**: 约 ¥50-100/月（新人优惠可低至 ¥30/月）

#### 2. 环境搭建

```bash
# SSH 登录
ssh root@<your-server-ip>

# 系统更新
apt update && apt upgrade -y

# 安装 Python 3.11+
apt install -y python3.11 python3.11-venv python3-pip nginx

# 创建项目目录
mkdir -p /opt/gaokao && cd /opt/gaokao

# 克隆代码（或 rsync 上传）
# rsync -avz --exclude='.git' --exclude='data/simadb/gaokao.db' D:/WorkBuddy/gaokao-database/ root@<ip>:/opt/gaokao/

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn[standard] python-dotenv requests

# 复制数据库
# scp data/simadb/gaokao.db root@<ip>:/opt/gaokao/data/simadb/
```

#### 3. 配置 .env

```bash
cat > /opt/gaokao/.env << 'EOF'
DEEPSEEK_API_KEY=sk-your-actual-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DB_PATH=data/simadb/gaokao.db
HOST=0.0.0.0
PORT=8000
EOF
```

#### 4. Systemd 服务

```bash
cat > /etc/systemd/system/gaokao.service << 'EOF'
[Unit]
Description=驷马报考 API Server
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/gaokao
Environment="PATH=/opt/gaokao/venv/bin"
ExecStart=/opt/gaokao/venv/bin/uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable gaokao
systemctl start gaokao
systemctl status gaokao
```

#### 5. Nginx 反向代理 + HTTPS

```bash
# 安装 certbot
apt install -y certbot python3-certbot-nginx

# Nginx 配置
cat > /etc/nginx/sites-available/gaokao << 'EOF'
server {
    listen 80;
    server_name gaokao.simafa.com;  # 替换为你的域名

    client_max_body_size 50M;

    # API 和前端
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 静态文件缓存
    location /static/ {
        proxy_pass http://127.0.0.1:8000;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

ln -s /etc/nginx/sites-available/gaokao /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 申请 SSL 证书
certbot --nginx -d gaokao.simafa.com
```

#### 6. 防火墙

```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

### 方案 B：Docker 部署

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 挂载数据卷
VOLUME ["/app/data"]

EXPOSE 8000

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  gaokao:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env:ro
    restart: always
    environment:
      - TZ=Asia/Shanghai
```

```bash
docker compose up -d
```

## 三、域名与 DNS

| 记录类型 | 主机记录 | 值 | TTL |
|---------|---------|-----|-----|
| A | gaokao | <服务器IP> | 600 |

推荐域名：`gaokao.simafa.com` 或 `gaokao.sima.com`

## 四、数据同步策略

### 本地 → 生产

```bash
# 定期同步数据库（每周一凌晨）
rsync -avz --compress \
  D:/WorkBuddy/gaokao-database/data/simadb/gaokao.db \
  root@<server>:/opt/gaokao/data/simadb/gaokao.db.new && \
ssh root@<server> "mv /opt/gaokao/data/simadb/gaokao.db.new /opt/gaokao/data/simadb/gaokao.db && systemctl restart gaokao"
```

### 生产环境自动采集（可选）

```bash
# crontab -e
0 3 * * * cd /opt/gaokao && venv/bin/python src/scripts/daily_run.py >> /var/log/gaokao-daily.log 2>&1
```

## 五、监控与日志

```bash
# 查看服务状态
systemctl status gaokao

# 查看实时日志
journalctl -u gaokao -f

# 查看访问日志
tail -f /var/log/nginx/access.log
```

## 六、API 端点一览

| 端点 | 说明 |
|------|------|
| `GET /api/health` | 健康检查 |
| `GET /api/stats` | 数据统计 |
| `GET /api/schools/search?q=xxx` | 院校搜索 |
| `GET /api/schools/suggest?q=xxx` | 院校建议 |
| `GET /api/admission/rank?score=600&province=浙江&year=2024` | 位次查询（含冲稳保） |
| `GET /api/admission/query?school_name=xxx` | 院校录取查询 |
| `GET /api/major/detail?major=xxx` | 专业详情 |
| `GET /api/reputation/{name}` | 院校口碑 |
| `GET /api/ask?q=xxx` | AI 问答 |
| `GET /static/index.html` | 前端页面 |

## 七、费用预估

| 项目 | 月费 |
|------|------|
| 阿里云轻量 2C4G | ¥50-100 |
| 域名（已有可复用） | ¥0 |
| SSL 证书（Let's Encrypt） | ¥0 |
| DeepSeek API（按用量） | ¥10-50 |
| **合计** | **¥60-150/月** |

## 八、下一步

1. **注册域名/子域名** → 配置 DNS A 记录
2. **购买服务器** → 按方案 A 部署
3. **上传数据库** → 验证服务
4. **配置 HTTPS** → 证书自动续期
5. **设置定时同步** → 保持数据更新
