#!/usr/bin/env python3
"""
DeepSeek V4 Pro 配置检查 + API 调用测试
用法: python3 check_deepseek_config.py
"""
import os
import sys
import json
import subprocess

# ═══════════════════════════════════════
# 第一部分：检查 .env 配置
# ═══════════════════════════════════════
print("=" * 60)
print("🔍 第一部分：检查 .env 配置文件")
print("=" * 60)

# 检查多个可能的路径
env_paths = [
    "/opt/ad-compliance-checker/.env",
    "/opt/ad-compliance-checker/backend/.env",
    "/opt/ad-compliance-checker/libang-custom/.env",
    "/opt/ad-compliance-checker/libang-custom/configs/.env",
]

found_key = None
for p in env_paths:
    if os.path.exists(p):
        print(f"  ✅ 找到 .env 文件: {p}")
        with open(p) as f:
            content = f.read().strip()
        if "DEEPSEEK_API_KEY" in content:
            # 提取 key（只显示前后4位）
            for line in content.split("\n"):
                if line.startswith("DEEPSEEK_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key:
                        found_key = key
                        masked = key[:6] + "****" + key[-4:]
                        print(f"  ✅ DEEPSEEK_API_KEY 已配置: {masked}")
                    else:
                        print(f"  ❌ DEEPSEEK_API_KEY 为空值!")
                    break
        else:
            print(f"  ❌ .env 文件中未找到 DEEPSEEK_API_KEY")
    else:
        print(f"  ❌ 未找到 .env 文件: {p}")

# 检查系统环境变量
sys_key = os.environ.get("DEEPSEEK_API_KEY", "")
if sys_key:
    masked = sys_key[:6] + "****" + sys_key[-4:]
    print(f"  ✅ 系统环境变量 DEEPSEEK_API_KEY 已设置: {masked}")
    if not found_key:
        found_key = sys_key
else:
    print(f"  ℹ️  系统环境变量 DEEPSEEK_API_KEY 未设置")

# 检查 main.py 或 systemd 服务中是否加载了 .env
print()
print("  📋 检查 uvicorn 服务配置...")
try:
    result = subprocess.run(
        ["systemctl", "cat", "ad-compliance-checker"],
        capture_output=True, text=True, timeout=5
    )
    if result.stdout:
        print(f"  ✅ 找到 systemd 服务配置:")
        for line in result.stdout.split("\n"):
            if "KEY" in line.upper() or "ENV" in line.upper() or "env" in line.lower() or ".env" in line.lower():
                print(f"     {line.strip()}")
    else:
        print(f"  ℹ️  未找到 ad-compliance-checker systemd 服务")
except:
    print(f"  ℹ️  无法查询 systemd 服务")

print()

# ═══════════════════════════════════════
# 第二部分：测试 API 调用
# ═══════════════════════════════════════
print("=" * 60)
print("🧪 第二部分：测试 DeepSeek V4 Pro API 调用")
print("=" * 60)

api_key = found_key or sys_key or os.environ.get("DEEPSEEK_API_KEY", "")
api_url = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
model = "deepseek-v4-pro"

if not api_key:
    print("  ❌ 未找到 API Key，无法测试")
    sys.exit(1)

print(f"  📡 API 地址: {api_url}")
print(f"  🤖 模型名称: {model}")
print(f"  🔑 API Key: {api_key[:6]}****{api_key[-4:]}")
print()

# 发送一个简单的测试请求
import urllib.request

payload = json.dumps({
    "model": model,
    "messages": [
        {"role": "system", "content": "你是一个测试助手，请用一句话回复。"},
        {"role": "user", "content": "回复「测试通过」四个字即可"}
    ],
    "temperature": 0.1,
    "max_tokens": 100,
}).encode("utf-8")

req = urllib.request.Request(
    api_url,
    data=payload,
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        print(f"  ✅ API 调用成功!")
        print(f"  💬 回复内容: {content}")
        print(f"  📊 Token 用量: 输入 {usage.get('prompt_tokens', '?')} + 输出 {usage.get('completion_tokens', '?')} = 总计 {usage.get('total_tokens', '?')}")
        print()
        print(f"  ✨ DeepSeek V4 Pro 配置正确，服务正常！")
except Exception as e:
    print(f"  ❌ API 调用失败: {e}")
    print()
    print(f"  💡 可能的原因:")
    print(f"     1. API Key 不正确")
    print(f"     2. 模型名称不对 (官方可能是 deepseek-v4-pro-202606)")
    print(f"     3. 网络不通（服务器无法访问 api.deepseek.com）")
    print(f"     4. 账户余额不足")
    sys.exit(1)
