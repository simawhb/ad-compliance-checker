# 驷马合规·广告自查助手 — 部署指南

## 一、环境要求

### 服务器
- 操作系统：Ubuntu 20.04+ / Windows Server 2019+
- Python：3.10+
- 内存：2GB+（初期100用户）
- 存储：20GB+
- 域名：需已备案（用于微信小程序）

### 依赖
```
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.5.0
pytesseract==0.3.10
Pillow==10.1.0
```

### 系统依赖（OCR）
```bash
# Ubuntu
sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim

# Windows
# 下载 Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
```

## 二、部署步骤

### 1. 安装依赖
```bash
pip install -r backend/requirements.txt
```

### 2. 配置域名和HTTPS
```bash
# 使用 Nginx 反向代理
server {
    listen 443 ssl;
    server_name api.your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. 启动服务
```bash
# 生产环境启动
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2

# 或使用 systemd 服务
sudo systemctl enable sima-compliance
sudo systemctl start sima-compliance
```

### 4. 微信小程序配置
- 在微信公众平台配置服务器域名：https://api.your-domain.com
- 配置业务域名和 request 合法域名
- 提交审核

## 三、数据安全

### 脱敏策略
- 不保存用户上传的广告文案原文
- 只保存检测统计信息（检测次数、时间、行业分类）
- 用户openid使用随机生成的匿名ID
- 定期清理30天前的统计日志

### 隐私合规
- 首次使用展示隐私协议
- 用户可随时删除账号和数据
- 不采集个人敏感信息

## 四、监控和运维

### 健康检查
```bash
curl https://api.your-domain.com/api/health
```

### 日志
- 服务器日志：uvicorn 自带
- 错误日志：server.err.log
- 访问统计：自建或接入百度统计

### 备份
```bash
# 每日备份数据库
cp users.db backups/users_$(date +%Y%m%d).db
```

## 五、扩展计划

### 第一阶段（100用户）
- 单机部署
- SQLite数据库
- 2个uvicorn worker

### 第二阶段（1000用户）
- 升级为PostgreSQL
- 4-8个worker
- 添加Redis缓存
- CDN加速静态资源

### 第三阶段（10000+用户）
- 负载均衡
- 数据库读写分离
- 微服务拆分
- 消息队列

