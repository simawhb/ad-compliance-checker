# 驷马用工宝 — 修复与界面分离部署说明

## 修改的文件清单

### 后端 (需上传到服务器)

| 文件 | 修改内容 |
|------|----------|
| `backend/app/api/v1/knowledge.py` | 新增 `GET /knowledge/laws/{title}` 端点，返回法律法规完整内容 |
| `backend/app/api/v1/template.py` | 新增 `GET /templates/{template_id}/download/{filename}` PDF下载端点 |
| `backend/app/api/v1/document.py` | 新增 `GET /documents/{doc_id}/download` PDF下载端点 |
| `backend/app/services/document_service.py` | 修复生成文书的 PDF 下载链接路径错误 |
| `backend/app/prompts/document_generate.py` | 修复 Prompt 占位符与前端表单字段不匹配问题（移除了前端不存在的字段） |

### 前端 (dist 目录需上传到服务器)

| 文件 | 修改内容 |
|------|----------|
| `dist/assets/index-BVrIjDqi.js` | 见下方详细说明 |

---

## JS 修改详细说明

### 1. 首页分离 — "选择服务模式"
- 标题从"劳动者维权 · 企业合规"改为"选择服务模式"
- 移除了热门标签（被辞退、拖欠工资等快速入口）
- 移除了"全部功能"网格（8个功能卡片）
- 首页仅保留两张大卡片：「劳动者端」和「企业端」，入口完全分离

### 2. 顶部导航简化
- 导航栏从混合的"维权 | 赔偿 | AI咨询 || 企业合规 | 成本"改为简洁的两入口
- 蓝色"劳动者维权"链接 → `/chat/labor`
- 绿色"企业合规"链接 → `/chat/enterprise`

### 3. 法规详情显示
- 点击法规条目后，从新端点 `/knowledge/laws/{title}` 获取完整内容
- 列表下方显示完整法规内容卡片（支持关闭）
- 替代原先从搜索接口获取断摘要的错误方式

### 4. 聊天页面增加标识
- 劳动者聊天页面增加"劳动者端"蓝色徽章
- 企业聊天页面保持原有"企业端"绿色徽章
- 用户在任何页面都能清楚识别当前模式

---

## 部署步骤

### 1. 上传后端文件到服务器
```bash
# SCP 到服务器 (118.190.133.215)
scp backend/app/api/v1/knowledge.py root@118.190.133.215:/opt/laobao/backend/app/api/v1/
scp backend/app/api/v1/template.py root@118.190.133.215:/opt/laobao/backend/app/api/v1/
scp backend/app/api/v1/document.py root@118.190.133.215:/opt/laobao/backend/app/api/v1/
scp backend/app/services/document_service.py root@118.190.133.215:/opt/laobao/backend/app/services/
scp backend/app/prompts/document_generate.py root@118.190.133.215:/opt/laobao/backend/app/prompts/

# 或者打包上传
scp backend/ root@118.190.133.215:/opt/laobao/
```

### 2. 上传前端文件到服务器
```bash
# 上传修改后的 JS
scp dist/assets/index-BVrIjDqi.js root@118.190.133.215:/opt/laobao/dist/assets/
```

### 3. 重启后端服务
```bash
ssh root@118.190.133.215
cd /opt/laobao/backend
# 重启 systemd 服务
systemctl restart laobao-backend
# 或手动重启
ps aux | grep uvicorn
kill -HUP <PID>
```

### 4. 验证
- 访问 https://4ma.wang/laobao/ → 看到"选择服务模式"两张卡片
- 点击"劳动者维权" → 进入劳动法咨询聊天（蓝色"劳动者端"徽章）
- 点击"企业合规" → 进入企业合规咨询（绿色"企业端"徽章）
- 点击"法规查询" → 搜索法规，点击条目查看完整内容
- 点击"协议模板" → 选择模板、填写信息、生成协议
