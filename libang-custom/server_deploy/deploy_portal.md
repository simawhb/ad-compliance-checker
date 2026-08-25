# 部署门户首页到服务器

SSH 连接后，在 Claude Code 中输入：

```
更新 /var/www/4ma.wang/index.html 为最新的门户首页，要求：

1. 标题：驷马工具集
2. 卡片列表包含以下工具（无图标，纯文字）：
   - 广告宣传审查助手 → https://checker.4ma.wang
   - 广告宣传审查助手 · 企业定制版 → /ad-check/
   - 高考志愿助手 → https://gaokao.4ma.wang
   - 驷马粮选 → /liangxuan/
   - C盘清理助手 → /c-clean/
   - 更多工具开发中（灰色占位）

3. 联系方式：wanghgbg@outlook.com
4. 底部备案号：陕ICP备2026017204号-1，链接到 https://beian.miit.gov.cn
5. 页脚添加服务分级说明表，包含：免费版 / 企业定制版 的 功能列表 和 适用场景 两列
6. 整体风格白色卡片网格布局，蓝色渐变头部，无 emoji 图标

写完后执行：nginx -t && systemctl reload nginx
确认 curl -sI https://4ma.wang 返回 200
```
