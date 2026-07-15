# Bug 修复部署指南

## Bug 1: 检测引擎使用了错误类别（化妆品而非 FSMP）

**原因**：`_match_forbidden_words()` 函数会遍历知识库中所有类别，包括化妆品类别。当检测特殊医学用途配方食品时，通用绝对化用语（如"最好""最先进""纯天然"）被化妆品类别捕获，错误标注为"化妆品违规词"。

**修复**：在 `detect()` 函数中添加行业类别排除机制，检测特医食品时跳过化妆品和医疗美容类别。

## Bug 2: 快速检测报 "Cannot read properties of undefined (reading 'score')"

**原因**：`sr(d)` 函数中 `d` 可能为 undefined 时直接访问 `d.score` 导致崩溃。

**修复**：在 `sr()` 函数开头添加 `if(!d)` 防御性检查。

---

## 部署步骤（在 Claude Code 中执行）

### 1. 修复 detector.py

```python
# 编辑 /opt/ad-checker-libang/backend/detector.py
# 在 detect() 函数上方添加行业排除映射：

# 行业 => 排除的类别映射（避免行业不相关的类别干扰检测结果）
_INDUSTRY_EXCLUDE_CATEGORIES = {
    "fsmp": {"cosmetics", "medical_beauty"},
    "food": {"cosmetics", "medical_beauty"},
    "cosmetic": set(),
    "medical": set(),
    "education": set(),
    "finance": set(),
    "realestate": set(),
}
```

修改 `detect()` 函数，将 `_match_forbidden_words(text)` 改为 `_match_forbidden_words(text, exclude_categories=exclude)`，并在函数开头添加：

```python
exclude = _INDUSTRY_EXCLUDE_CATEGORIES.get(industry, set())
```

修改 `_match_forbidden_words()` 函数签名，添加 `exclude_categories=None` 参数，在循环中添加跳过逻辑：

```python
if exclude_categories and cat_key in exclude_categories:
    continue
```

### 2. 修复 frontend/index.html

在 `sr(d)` 函数开头添加空值检查：

```javascript
function sr(d){if(!d){se('返回数据异常，请重试');return}...}
```

### 3. 重启服务

```bash
systemctl restart ad-checker-libang
```

### 4. 验证

```bash
# 查看启动日志
journalctl -u ad-checker-libang -n 20 --no-pager

# 测试 API
curl -s http://127.0.0.1:8001/api/health
```
