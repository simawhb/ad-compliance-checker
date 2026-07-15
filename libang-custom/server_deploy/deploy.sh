#!/bin/bash
# ============================================================
# 4ma.wang 部署脚本 — 王老师的工具集 + 力邦广告审查助手
# 使用方法: sudo bash deploy.sh
# 适用系统: Ubuntu 20.04+ / Debian 11+
# ============================================================
set -e

echo "=========================================="
echo "  4ma.wang 部署脚本"
echo "=========================================="

# ---- 配置 ----
PORTAL_DIR="/var/www/4ma.wang"
LIBANG_DIR="/opt/ad-checker-libang"
NGINX_CONF_SRC="$(dirname "$0")/nginx_4ma.wang.conf"
NGINX_CONF_DST="/etc/nginx/sites-available/4ma.wang"

# ---- 检查 root ----
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请以 root 权限运行: sudo bash deploy.sh"
    exit 1
fi

# ---- 步骤 1: 部署门户首页 ----
echo ""
echo "[1/6] 部署门户首页 → $PORTAL_DIR"
mkdir -p "$PORTAL_DIR"
cp "$(dirname "$0")/../4ma_wang_portal.html" "$PORTAL_DIR/index.html"
echo "  ✅ 门户首页已部署"

# ---- 步骤 2: 部署力邦版后端 ----
echo ""
echo "[2/6] 部署力邦广告审查助手 → $LIBANG_DIR"

# 检查是否已有旧版本
if [ -d "$LIBANG_DIR/backend" ]; then
    echo "  ⚠️  检测到已有版本，备份中..."
    BACKUP_DIR="/opt/ad-checker-libang-backup-$(date +%Y%m%d%H%M%S)"
    cp -a "$LIBANG_DIR" "$BACKUP_DIR"
    echo "  ✅ 已备份到 $BACKUP_DIR"
fi

# 复制文件（当前脚本所在目录的上一级是 libang-custom 根目录）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIBANG_SRC="$(cd "$SCRIPT_DIR/.." && pwd)"

# 排除不需要的目录
rsync -av --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='venv' \
    --exclude='.venv' \
    --exclude='node_modules' \
    --exclude='server_deploy' \
    --exclude='*.pyc' \
    --exclude='package_for_client.py' \
    "$LIBANG_SRC/" "$LIBANG_DIR/"
echo "  ✅ 力邦版代码已部署"

# ---- 步骤 3: 安装 Python 依赖 ----
echo ""
echo "[3/6] 安装 Python 依赖"
if [ ! -d "$LIBANG_DIR/venv" ]; then
    echo "  ⏳ 创建虚拟环境..."
    python3 -m venv "$LIBANG_DIR/venv"
fi
source "$LIBANG_DIR/venv/bin/activate"
pip install -r "$LIBANG_DIR/backend/requirements.txt" --quiet
pip install aiofiles jinja2 --quiet
deactivate
echo "  ✅ Python 依赖已安装"

# ---- 步骤 4: 设置访问密码（力邦专属） ----
echo ""
echo "[4/6] 设置力邦版访问密码"
echo "  请为力邦营养设置访问用户名和密码"
echo "  （这个密码会提示给访问 /ad-check/ 的用户）"
echo ""
read -p "  用户名 (推荐: libang): " LB_USER
if [ -z "$LB_USER" ]; then
    LB_USER="libang"
fi
echo "  请输入密码（至少 6 位）:"
read -s LB_PASS1
echo ""
echo "  请再次输入密码:"
read -s LB_PASS2
echo ""
if [ "$LB_PASS1" != "$LB_PASS2" ]; then
    echo "  ❌ 两次密码不一致，请重新运行脚本"
    exit 1
fi
if [ ${#LB_PASS1} -lt 6 ]; then
    echo "  ❌ 密码长度不足 6 位，请重新运行脚本"
    exit 1
fi

# 生成 htpasswd 文件（使用 openssl）
if command -v openssl &> /dev/null; then
    HASH=$(openssl passwd -apr1 "$LB_PASS1")
    echo "$LB_USER:$HASH" > /etc/nginx/.htpasswd_libang
    echo "  ✅ 密码已设置（用户名: $LB_USER）"
else
    echo "  ❌ 未找到 openssl，请手动创建 htpasswd 文件"
    echo "     apt install openssl 或使用:"
    echo "     printf '$LB_USER:\$(openssl passwd -apr1)' > /etc/nginx/.htpasswd_libang"
    exit 1
fi

# ---- 步骤 5: 配置 Nginx ----
echo ""
echo "[5/6] 配置 Nginx"
if [ -f "$NGINX_CONF_DST" ]; then
    cp "$NGINX_CONF_DST" "${NGINX_CONF_DST}.bak"
    echo "  ⚠️  备份原配置"
fi
cp "$NGINX_CONF_SRC" "$NGINX_CONF_DST"

# 启用站点
if [ ! -L "/etc/nginx/sites-enabled/4ma.wang" ]; then
    ln -sf "$NGINX_CONF_DST" "/etc/nginx/sites-enabled/4ma.wang"
fi

# 测试配置
nginx -t
echo "  ✅ Nginx 配置测试通过"

# 重启
systemctl reload nginx || systemctl restart nginx
echo "  ✅ Nginx 已重启"

# ---- 步骤 6: 配置 systemd 服务 ----
echo ""
echo "[6/6] 注册 systemd 服务"
cp "$(dirname "$0")/ad-checker-libang.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable ad-checker-libang
systemctl restart ad-checker-libang
echo "  ✅ systemd 服务已启动"

# ---- 完成 ----
echo ""
echo "=========================================="
echo "  🎉 部署完成！"
echo "=========================================="
echo ""
echo "  门户首页:    https://4ma.wang"
echo "  力邦审查助手: https://4ma.wang/ad-check/"
echo "  力邦访问密码: (刚才设置的用户名/密码)"
echo ""
echo "  查看服务状态:"
echo "    systemctl status ad-checker-libang"
echo ""
echo "  查看日志:"
echo "    journalctl -u ad-checker-libang -f"
echo ""
echo "=========================================="
