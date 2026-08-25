# 服务器 Claude Code 提示词模板

> 使用方法：SSH 连上服务器后运行 `claude`，粘贴对应提示词即可。

---

## 一、日常健康检查

**用途：** 每天早上或每周手动检查一次，确认服务正常运行。

```
请对服务器进行一次全面健康检查，输出以下内容：

## 1. 服务状态
- systemctl status ad-checker --no-pager -l
- systemctl status ad-checker-libang --no-pager -l
- systemctl status nginx --no-pager -l
标记出任何不是 running 的服务

## 2. 磁盘使用率
df -h /   关注是否超过 80%

## 3. 内存使用率
free -h   关注剩余内存

## 4. SSL 证书到期时间
检查 /etc/letsencrypt/live/ 下每个域名的证书到期日

## 5. 端口监听情况
ss -tlnp | grep -E "8000|8001|80|443"

## 6. Nginx 错误日志
tail -20 /var/log/nginx/error.log

请用表格格式输出检查结果，有问题的项目标记 ❌
```

---

## 二、部署新版代码

**用途：** 本地代码更新后，部署到服务器。

```
请执行以下部署操作：

## 部署新版广告审查助手
1. 进入 /opt/ad-checker-libang/ 目录
2. 用 git pull 拉取最新代码（如果没有 git，则从 /tmp/ 下的 tar.gz 包解压）
3. 如果 requirements.txt 有变化，重新安装依赖：
   source venv/bin/activate && pip install -r backend/requirements.txt && deactivate
4. 重启服务：systemctl restart ad-checker-libang

## 部署门户页面
1. 将新的 4ma_wang_portal.html 复制到 /var/www/4ma.wang/index.html

## 部署原版审查助手
1. 进入 /opt/ad-compliance-checker/
2. git pull 或更新代码
3. 重启服务：systemctl restart ad-checker

执行完后验证：
- curl -s -o /dev/null -w "%{http_code}" https://4ma.wang
- curl -s -o /dev/null -w "%{http_code}" -u libang:libang2026 https://4ma.wang/ad-check/
- curl -s -o /dev/null -w "%{http_code}" https://checker.4ma.wang
全部返回 200 才算成功
```

---

## 三、SSL 证书检查与续期

**用途：** 检查证书到期情况，手动续期。

```
1. 列出所有 Let's Encrypt 证书：
   certbot certificates

2. 检查每个证书的到期日，如果 30 天内到期则续期：
   certbot renew --dry-run 先测试
   如果测试通过，执行 certbot renew

3. 续期后重载 Nginx：
   systemctl reload nginx

4. 验证各域名 HTTPS 正常：
   curl -s -o /dev/null -w "%{http_code}" https://4ma.wang
   curl -s -o /dev/null -w "%{http_code}" https://checker.4ma.wang
```

---

## 四、安全检查

**用途：** 定期检查服务器安全状况。

```
请执行安全审计并输出结果：

## 1. 防火墙规则
ufw status verbose

## 2. 检查是否有非 root 的 sudo 用户
grep -Po '^sudo:.*$' /etc/group

## 3. 检查最近失败的 SSH 登录
lastb | head -20

## 4. 检查异常进程
ps aux --sort=-%mem | head -10

## 5. 检查系统更新
apt list --upgradable 2>/dev/null | head -20

## 6. 检查对外开放的端口
ss -tlnp | grep -E "0.0.0.0:|:::" | grep -v "127.0.0.1"

## 7. 检查 Nginx 配置文件有无安全隐患
grep -r "server_tokens" /etc/nginx/
grep -r "ssl_protocols" /etc/nginx/

输出安全评分及改进建议
```

---

## 五、查看日志排查问题

**用途：** 用户反馈网站异常时排查。

```
请帮我排查问题：

## 1. 最近的服务日志
journalctl -u ad-checker -n 30 --no-pager
journalctl -u ad-checker-libang -n 30 --no-pager

## 2. Nginx 最近错误
tail -30 /var/log/nginx/error.log

## 3. Nginx 最近访问日志（只显示非 200 的）
tail -100 /var/log/nginx/access.log | grep -v ' 200 ' | grep -v ' 301 '

## 4. 当前所有服务状态
systemctl list-units --type=service --state=running

## 5. 磁盘和内存使用
df -h /
free -h

分析日志中的异常模式并给出修复建议
```

---

## 六、修改 Nginx 配置

**用途：** 调整网站路由、代理规则等。

```
请帮我修改 Nginx 配置：

1. 备份当前配置：
   cp /etc/nginx/sites-available/ad-checker /etc/nginx/sites-available/ad-checker.bak.$(date +%Y%m%d%H%M%S)

2. [在这里描述你要改的内容]

3. 测试配置：
   nginx -t

4. 重新加载：
   systemctl reload nginx

5. 验证：
   curl -s -o /dev/null -w "%{http_code}" https://4ma.wang
   curl -s -o /dev/null -w "%{http_code}" https://checker.4ma.wang
```

> 使用前把第 2 步的 [ ] 替换成具体需求

---

## 七、服务器初始化（新服务器用）

**用途：** 全新的 Ubuntu 服务器，从头部署所有服务。

```
请在新服务器上执行完整部署：

## 1. 安装基础软件
apt update && apt install -y nginx python3 python3-pip python3-venv certbot

## 2. 创建目录结构
mkdir -p /opt/ad-checker-libang /var/www/4ma.wang /var/www/download

## 3. 部署力邦版
[从部署包解压到 /opt/ad-checker-libang/]
python3 -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt
pip install aiofiles jinja2
deactivate

## 4. 创建 Nginx 配置
[复制 nginx_4ma.wang.conf 到 /etc/nginx/sites-available/ad-checker]
ln -sf /etc/nginx/sites-available/ad-checker /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

## 5. 申请 SSL 证书
certbot --nginx -d 4ma.wang -d www.4ma.wang --agree-tos -m wanghgbg@outlook.com

## 6. 注册系统服务
[复制 ad-checker-libang.service 到 /etc/systemd/system/]
systemctl daemon-reload && systemctl enable ad-checker-libang && systemctl start ad-checker-libang

## 7. 设置力邦版密码
htpasswd -c /etc/nginx/.htpasswd_libang libang
[交互式输入密码]

## 8. 最终验证
```

---

## 八、定时任务：每日巡检

**用途：** 每天自动检查服务器状态。

```bash
# 保存为 /opt/scripts/health_check.sh，添加到 crontab
```

我建议设置一个每天早上的自动巡检任务，要不要我帮你设定？这样每天早上 8 点服务器会自动检查一次，有问题会通知你。
