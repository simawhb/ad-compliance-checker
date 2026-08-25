# 独立部署准备包

本目录保存可复用部署模板。`draft.4ma.wang` 已于 2026-08-09 按该独立服务方案部署；模板不包含真实密钥、证书或服务器备份。

## 设计结论

- 使用独立子域名 `draft.4ma.wang` 和独立端口 `8012`，不触碰现有广告审查服务、桌面版或既有 API。
- 服务仅监听 `127.0.0.1`，由 Nginx 转发；使用单 worker，内存上限 `256M`。
- 起草接口限制为每 IP 每分钟 6 次、突发 2 次；请求体上限 `64k`。
- 关闭访问日志，避免保存 IP 和提交内容；错误日志不得输出请求体、密钥或文案。

## 模板文件

| 文件 | 用途 |
|---|---|
| `draft-service.env.example` | 受控环境变量清单，不含真实密钥 |
| `sima-draft.service` | systemd 单进程、低权限服务模板 |
| `sima-draft-limits.nginx.conf` | Nginx `http` 级限流共享区 |
| `sima-draft-http.nginx.conf.example` | 首次签发证书前的 HTTP 验证站点 |
| `sima-draft.nginx.conf.example` | HTTPS、限流、超时和回环代理正式配置 |

## 上线前检查

1. 正式子域名已确定为 `draft.4ma.wang`；上线时单独申请证书并新建 Nginx 站点，不得拼入现有审查站点。
2. 创建仅供服务使用的系统账户、受控环境文件和只读规则库副本。
3. 在服务器先验证 `/api/health`、五类脱敏验收、移动端页面和内存占用。
4. 备份现有 Nginx 配置及 `ad-checker.service`；只有新服务独立通过后才添加新站点。
5. 最后回归旧审查助手的首页、`/pc/`、`/m/`、`/api/health` 和快速检测。

未获明确上线授权前，不执行复制、安装、重载 Nginx、创建服务或公开 DNS 操作。
