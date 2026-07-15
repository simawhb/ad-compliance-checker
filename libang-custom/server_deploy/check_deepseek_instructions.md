# DeepSeek V4 Pro 服务器配置检查指引

## 操作步骤

在服务器上依次执行以下命令：

### 1. 创建检测脚本

```bash
cat > /tmp/check_deepseek.py << 'PYEOF'
#!/usr/bin/env python3
import os, sys, json, urllib.request

print("=" * 60)
print("第一部分：检查 .env 配置文件")
print("=" * 60)

env_paths = [
    "/opt/ad-compliance-checker/.env",
    "/opt/ad-compliance-checker/backend/.env",
    "/opt/ad-compliance-checker/libang-custom/.env",
    "/opt/ad-compliance-checker/libang-custom/configs/.env",
]

found_key = None
for p in env_paths:
    if os.path.exists(p):
        print(f"  [OK] 找到 .env: {p}")
        with open(p) as f:
            content = f.read().strip()
        if "DEEPSEEK_API_KEY" in content:
            for line in content.split("\n"):
                if line.startswith("DEEPSEEK_API_KEY="):
                    key = line.split("=",1)[1].strip().strip('"').strip("'")
                    if key:
                        found_key = key
                        print(f"  [OK] API Key: {key[:6]}****{key[-4:]}")
                    else:
                        print(f"  [ERR] API Key 为空!")
        else:
            print(f"  [ERR] 文件中无 DEEPSEEK_API_KEY")
    else:
        print(f"  [..] 无此文件: {p}")

sys_key = os.environ.get("DEEPSEEK_API_KEY", "")
if sys_key:
    print(f"  [OK] 系统环境变量: {sys_key[:6]}****{sys_key[-4:]}")
    if not found_key:
        found_key = sys_key
else:
    print(f"  [..] 系统环境变量未设置 DEEPSEEK_API_KEY")

api_key = found_key or sys_key
api_url = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
model = "deepseek-v4-pro"

if not api_key:
    print("\n  [ERR] 未找到任何 API Key，退出")
    sys.exit(1)

print()
print("=" * 60)
print("第二部分：测试 DeepSeek V4 Pro API")
print("=" * 60)
print(f"  API: {api_url}")
print(f"  Model: {model}")

payload = json.dumps({
    "model": model,
    "messages": [
        {"role": "system", "content": "你是一个测试助手"},
        {"role": "user", "content": "回复「测试通过」四字即可"}
    ],
    "temperature": 0.1,
    "max_tokens": 100,
}).encode()

req = urllib.request.Request(
    api_url, data=payload,
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        print(f"\n  [OK] API 调用成功!")
        print(f"  回复: {content}")
        print(f"  Token: {usage}")
except Exception as e:
    print(f"\n  [ERR] API 调用失败: {e}")
    print(f"\n  可能原因: 1) Key 不正确 2) 模型名不对 3) 网络不通 4) 余额不足")
PYEOF
```

### 2. 运行检测

```bash
python3 /tmp/check_deepseek.py
```

### 3. 查看结果

检测脚本会输出两大部分结果：
- **第一部分**: 服务器上 .env 文件位置和 API Key 配置状态
- **第二部分**: 实际调用 DeepSeek V4 Pro API 的测试结果

### 4. 如果 API 调用失败

尝试更换模型名（V4 正式版可能不同）：

```bash
# 用不同模型名重试
sed -i 's/deepseek-v4-pro/deepseek-v4-pro-202606/' /tmp/check_deepseek.py && python3 /tmp/check_deepseek.py
```

或者查看 DeepSeek 官方最新模型名：
```bash
curl -s https://api.deepseek.com/v1/models -H "Authorization: Bearer $(grep DEEPSEEK_API_KEY /opt/ad-compliance-checker/.env | cut -d= -f2 | tr -d '\"')" | python3 -m json.tool 2>/dev/null || echo "无法获取模型列表"
```

把输出结果发给我，我帮你分析。
