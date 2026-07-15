# 驷马粮选 · V3 暖色包装风部署说明

## 操作方式

SSH 登录服务器后执行 `claude`，然后把下面的步骤粘贴给 Claude Code 执行。

---

## 操作步骤

### 1. 查看当前源码结构

```bash
ls -la /opt/simaliangxuan/
```

确认首页文件位置（可能是 `index.html`、`templates/index.html` 或 `public/index.html`）。

### 2. 替换样式

找到首页 HTML 文件，将其中的 `<style>...</style>` 部分整体替换为下面的 V3 样式。

### 3. 需要修改的关键部分

**头部** — 将原深蓝/白色头部改为暖色渐变
- 背景: `linear-gradient(160deg, #631e0e 0%, #8a3420 40%, #a84b2a 100%)`
- 标题颜色: `#fdf6ee`
- 金色装饰条: `#e8c658`

**搜索栏** — 搜索按钮改为金色
- 背景: `linear-gradient(135deg, #e8c658, #d4a840)`
- 文字: `#4a1608`

**标签** — 全部加上底色
- 优选推荐: 深栗底金字 `(#631e0e → #8a3420 / #fdf6ee)`
- 热销爆款: 金底深棕 `(#e8c658 / #4a1608)`
- 更新标签: 蓝底 `(#e0edff / #1e40af)`
- 警告标签: 红底 `(#fee7e7 / #b91c1c)`

**功能入口卡片** — 白底、暖色描边、hover 上浮

**统计卡片** — 顶部加渐变装饰条

> 完整样式参考已在本地保存：`D:\驷马仓库\ad-compliance-checker\libang-custom\simaliangxuan_preview.html`

### 4. 部署完成后的验证

- 访问 https://4ma.wang/liangxuan/ 确认样式正确
- 确认所有标签有底色，文字清晰可读
- 确认没有 emoji 图标残留
- 确认移动端显示正常

---

部署完成后告诉我结果。
