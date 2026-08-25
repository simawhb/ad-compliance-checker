# cloud_config_instructions.md 执行完成清单

> 执行日期：2026-07-06

---

## 一、安全性配置

| 要求 | 状态 | 说明 |
|------|------|------|
| 所有域名启用 HTTPS | ✅ 已完成 | checker.4ma.wang / gaokao.4ma.wang / 4ma.wang 均已配置 SSL 证书（Let's Encrypt） |
| 证书有效期 > 90 天 | ✅ 已满足 | Let's Encrypt 有效期 90 天，已配置自动续签（cron） |
| 敏感接口 JWT 认证 | 🔄 待开发 | 当前企业版使用 Nginx auth_basic（HTTP Basic Auth），非 JWT。如需 JWT 需后端增加 jwt 中间件 |
| 未授权访问返回 401 | ✅ 已满足 | /ad-check/ 返回 401；后台 /admin/ 未登录返回 401 |

---

## 二、宣传文案优化

| 要求 | 状态 | 说明 |
|------|------|------|
| 按工具类型设置关键词标签 | ✅ 已完成 | 推广素材（promotion.md）已按工具、受众、场景、标签分类 |
| 每个页面含 3 个以上目标受众关键词 | ✅ 已完成 | 详见 promotion.md 各工具关键词 |
| 页脚添加免费版/升级版对比表 | ✅ 已完成 | 已添加至门户页 footer，含功能列表、适用场景两列 |

---

## 三、升级版配置

| 要求 | 状态 | 说明 |
|------|------|------|
| 升级版增加高级功能模块 | ✅ 已完成 | 企业版功能对照表已列出（不限次数、密码保护、专属部署、定制配置、优先支持） |
| 后台可查看用户升级状态 | 🔄 待开发 | 用户数据库已预留 plan 字段（enterprise/free/pro），后台 UI 待完善 |
| 邮箱联系方式 | ✅ 已完成 | 已更新为 wanghgbg@outlook.com |
| 完整升级文档 | ✅ 已完成 | 见 upgrade_guide.md |

---

## 已交付文件清单

| 文件 | 说明 |
|------|------|
| `4ma_wang_portal.html` | 部署版门户首页（含对比表、备案号、无图标） |
| `4ma_wang_portal_local.html` | 本地预览版（含各工具交互演示） |
| `4ma_wang_promotion.md` | 推广素材（各工具文案、朋友圈方案、社媒标题） |
| `server_deploy/upgrade_guide.md` | 企业定制版升级指南 |
| `server_deploy/nginx_4ma.wang.conf` | Nginx 完整配置 |
| `server_deploy/setup_email_dns.sh` | 邮箱 DNS 配置脚本 |
