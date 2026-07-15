"""测试力邦定制版 API"""
import urllib.request, json

BASE = "http://127.0.0.1:8002"
openid = "libe_test_001"

tests = [
    {"name": "快速检测（普通食品）", "data": {"text": "本品采用天然原料，绝对安全无副作用，效果最佳，全国第一", "industry": "food", "platform": "", "openid": openid}},
    {"name": "快速检测（特医食品）", "data": {"text": "本产品可替代日常饮食，能治疗各种疾病，效果显著", "industry": "fsmp", "platform": "", "openid": openid}},
    {"name": "单个违禁词检测", "data": {"text": "全网最高品质，质量最好，国家级认证产品", "industry": "", "platform": "", "openid": openid}},
]

passed = 0
failed = 0

for t in tests:
    print(f"\n{'='*50}")
    print(f"测试: {t['name']}")
    print(f"文案: {t['data']['text']}")
    print(f"{'='*50}")

    try:
        req = urllib.request.Request(
            f"{BASE}/api/check",
            data=json.dumps(t["data"]).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode("utf-8"))

        if result.get("ok"):
            score = result.get("score", 0)
            risks = result.get("risk_count", 0)
            print(f"  ✅ 检测成功 | 评分: {score} | 风险项: {risks}")
            for r in result.get("risks", [])[:3]:
                print(f"     - {r.get('word', '')} ({r.get('category', '')})")
            passed += 1
        else:
            print(f"  ❌ 检测失败: {result.get('error', '未知错误')}")
            failed += 1
    except Exception as e:
        print(f"  ❌ 请求异常: {e}")
        failed += 1

print(f"\n{'='*50}")
print(f"测试完成: ✅ {passed} 通过, ❌ {failed} 失败")
print(f"{'='*50}")
