#!/bin/bash
# =============================================================================
# 驷马报考 — 服务器一键部署脚本
# 目标: https://gaokao.4ma.wang（子域名，DNS 通配符已覆盖）
# 内部端口: 8001（与广告审查助手 8000 不冲突）
# 项目路径: /opt/gaokao-database/
# 运行方式: 上传到服务器后 bash deploy_gaokao.sh
# =============================================================================

set -e

echo "========================================="
echo "  驷马报考 服务器部署"
echo "  系统: $(lsb_release -ds 2>/dev/null || cat /etc/os-release 2>/dev/null | head -1)"
echo "  IP:   $(curl -s ifconfig.me 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')"
echo "========================================="

# ---- 0. 检查环境 ----
echo ""
echo "[0/6] 检查环境..."

if [ "$(id -u)" -ne 0 ]; then
    echo "  ❌ 请以 root 用户执行 (sudo -i 或 su root)"
    exit 1
fi

PY_VER=$(python3 --version 2>/dev/null || echo "未安装")
echo "  ✓ Python: $PY_VER"

# ---- 1. 创建项目目录 ----
echo ""
echo "[1/6] 创建项目目录..."

mkdir -p /opt/gaokao-database/{data/simadb,data/raw,logs,reports/daily}
echo "  ✓ 目录已创建: /opt/gaokao-database/"

# ---- 2. 配置 .env ----
echo ""
echo "[2/6] 写入 .env 配置..."

cat > /opt/gaokao-database/.env << 'ENVEOF'
# 驷马报考 环境配置
DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
HOST=127.0.0.1
PORT=8001
RELOAD=false
LOG_LEVEL=info
CORS_ORIGINS=https://gaokao.4ma.wang
DB_PATH=data/simadb/gaokao.db
ENVEOF

echo "  ✓ .env 已写入"

# ---- 3. 安装系统依赖 ----
echo ""
echo "[3/6] 安装系统依赖..."

apt update -qq
apt install -y -qq python3-pip python3-venv nginx certbot python3-certbot-nginx 2>&1 | tail -3
apt install -y -qq libgtk-3-0 libnss3 libx11-xcb1 libgbm1 libasound2 2>&1 | tail -3 || true
echo "  ✓ 系统依赖安装完成"

# ---- 4. 安装 Python 依赖 ----
echo ""
echo "[4/6] 安装 Python 依赖..."

cd /opt/gaokao-database

# 如果代码还没上传，先创建 requirements.txt
if [ ! -f requirements.txt ]; then
    cat > requirements.txt << 'REQEOF'
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
httpx>=0.27.0
python-dotenv>=1.0.0
xlrd>=2.0.0
REQEOF
fi

pip3 install --break-system-packages -r requirements.txt 2>&1 | tail -5
echo "  ✓ Python 依赖安装完成"

# ---- 5. systemd 服务 ----
echo ""
echo "[5/6] 配置 systemd 自启服务..."

cat > /etc/systemd/system/gaokao.service << 'SERVICEEOF'
[Unit]
Description=驷马报考 API Server
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/gaokao-database
ExecStart=/usr/bin/python3 src/api/app.py
Restart=always
RestartSec=5
StandardOutput=append:/opt/gaokao-database/logs/api.log
StandardError=append:/opt/gaokao-database/logs/api.log

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable gaokao.service
echo "  ✓ systemd 服务已配置 (gaokao)"

# ---- 6. Nginx 配置（子域名方案） ----
echo ""
echo "[6/6] 配置 Nginx 反向代理..."

NGINX_SITE="/etc/nginx/sites-available/gaokao"
NGINX_ENABLED="/etc/nginx/sites-enabled/gaokao"

# 如果已存在 gaokao 配置，先确认
if [ -f "$NGINX_SITE" ]; then
    echo "  ⚠️ 已存在 gaokao Nginx 配置，将覆盖"
fi

cat > "$NGINX_SITE" << 'NGINXEOF'
server {
    listen 80;
    server_name gaokao.4ma.wang;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name gaokao.4ma.wang;

    # SSL（复用主域名的证书）
    ssl_certificate /etc/letsencrypt/live/4ma.wang/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/4ma.wang/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # 安全头
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";

    client_max_body_size 10M;

    # API + 前端
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 静态文件缓存
    location /static/ {
        proxy_pass http://127.0.0.1:8001/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # 隐藏 API 文档
    location = /docs { return 404; }
    location = /redoc { return 404; }
    location = /openapi.json { return 404; }
}
NGINXEOF

# 启用站点
ln -sf "$NGINX_SITE" "$NGINX_ENABLED"

# 扩展 SSL 证书，增加 gaokao.4ma.wang
echo "  正在扩展 SSL 证书..."
certbot --nginx -d 4ma.wang -d www.4ma.wang -d gaokao.4ma.wang --non-interactive --agree-tos -m 14712502@qq.com 2>&1 || {
    echo "  ⚠️ 证书扩展失败，尝试仅用已有证书..."
    echo "  手动执行: certbot --nginx -d 4ma.wang -d www.4ma.wang -d gaokao.4ma.wang"
}

# 检查 Nginx 配置
if nginx -t 2>&1; then
    systemctl reload nginx
    echo "  ✓ Nginx 已重新加载"
else
    echo "  ❌ Nginx 配置错误:"
    nginx -t 2>&1
    exit 1
fi

# ---- 完成 ----
echo ""
echo "========================================="
echo "  🎉 部署环境配置完成！"
echo "========================================="
echo ""
echo "  接下来还需要两步："
echo ""
echo "  ─── 第一步：上传代码 ───"
echo "  在本机 PowerShell 执行："
echo ""
echo "  rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \\"
echo "    --exclude='.gitignore' \\"
echo "    D:/驷马仓库/ad-compliance-checker/gaokao/ \\"
echo "    root@118.190.133.215:/opt/gaokao-database/"
echo ""
echo "  ─── 第二步：上传数据库 ───"
echo "  rsync -avz \\"
echo "    D:/驷马仓库/ad-compliance-checker/gaokao/data/simadb/gaokao.db \\"
echo "    root@118.190.133.215:/opt/gaokao-database/data/simadb/gaokao.db"
echo ""
echo "  ─── 第三步：启动服务 ───"
echo "  systemctl start gaokao"
echo "  systemctl status gaokao"
echo ""
echo "  ─── 第四步：验证 ───"
echo "  curl https://gaokao.4ma.wang/api/health"
echo "  或者浏览器打开 https://gaokao.4ma.wang"
echo ""
echo "  ─── 查看日志 ───"
echo "  journalctl -u gaokao -n 50 -f"
echo "  tail -f /opt/gaokao-database/logs/api.log"
echo ""
echo "========================================="
