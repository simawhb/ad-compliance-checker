# 4ma.wang 服务器部署说明

## 部署前准备

1. 确保服务器已安装：
   - Nginx
   - Python 3.9+
   - Git（可选）

2. 将本目录（`server_deploy/`）及上一级目录（`libang-custom/` 所有内容）上传到服务器

## 一键部署

```bash
# 进入部署目录
cd /path/to/server_deploy

# 以 root 权限运行部署脚本
sudo bash deploy.sh
```

部署脚本会自动完成：
1. 部署门户首页到 `/var/www/4ma.wang/`
2. 部署力邦审查助手到 `/opt/ad-checker-libang/`
3. 安装 Python 依赖
4. 设置力邦访问密码（交互式输入）
5. 配置 Nginx 子路径路由
6. 注册 systemd 服务

## 手动步骤（如果不使用一键脚本）

### 1. 部署门户首页

```bash
mkdir -p /var/www/4ma.wang
cp 4ma_wang_portal.html /var/www/4ma.wang/index.html
```

### 2. 部署力邦后端

```bash
mkdir -p /opt/ad-checker-libang
# 将 libang-custom/ 下所有内容（除 server_deploy/）复制到 /opt/ad-checker-libang/
rsync -av --exclude='server_deploy' --exclude='.git' --exclude='__pycache__' /path/to/libang-custom/ /opt/ad-checker-libang/

# 安装依赖
cd /opt/ad-checker-libang
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
pip install aiofiles jinja2
deactivate
```

### 3. 设置访问密码

```bash
# 安装 openssl（如果未安装）
apt install openssl

# 创建密码（交互式）
openssl passwd -apr1

# 将输出写入文件
echo "libang:$HASH" > /etc/nginx/.htpasswd_libang
```

### 4. 配置 Nginx

```bash
cp nginx_4ma.wang.conf /etc/nginx/sites-available/4ma.wang
ln -sf /etc/nginx/sites-available/4ma.wang /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### 5. 注册系统服务

```bash
cp ad-checker-libang.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable ad-checker-libang
systemctl start ad-checker-libang
```

### 6. 配置 API Key（可选）

```bash
echo "DEEPSEEK_API_KEY=sk-your-key-here" > /opt/ad-checker-libang/.env
```

## 验证部署

- 门户首页：https://4ma.wang
- 力邦审查助手：https://4ma.wang/ad-check/（需要密码）
- 检查服务状态：`systemctl status ad-checker-libang`
- 查看日志：`journalctl -u ad-checker-libang -f`

## 后续维护

### 查看日志
```bash
journalctl -u ad-checker-libang -f --tail=50
```

### 更新代码
```bash
systemctl stop ad-checker-libang
rsync -av --delete /path/to/new-code/ /opt/ad-checker-libang/ --exclude='venv' --exclude='.env'
systemctl start ad-checker-libang
```

### 修改密码
```bash
openssl passwd -apr1
# 用新哈希替换 /etc/nginx/.htpasswd_libang 中的内容
systemctl reload nginx
```

## 目录结构（部署后）

```
/var/www/4ma.wang/
  └── index.html                  # 门户首页
/opt/ad-checker-libang/
  ├── start_server.py             # 本地启动脚本
  ├── start_server_prod.py        # 生产启动脚本（端口 8001）
  ├── backend/
  ├── frontend/
  ├── h5/
  ├── batch/
  ├── knowledge/
  ├── data/
  └── venv/
/etc/nginx/
  ├── sites-available/4ma.wang    # Nginx 站点配置
  └── .htpasswd_libang            # 力邦版访问密码
/etc/systemd/system/
  └── ad-checker-libang.service   # systemd 服务
```
