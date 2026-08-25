import asyncio
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import httpx  # noqa: E402
import weiquan_consumer_service as service  # noqa: E402
from weiquan_business import (  # noqa: E402
    DISCLAIMER,
    BusinessAnalysisService,
    InvalidBusinessResponseError,
    parse_and_validate,
)


VALID = {
    "disputeType": "当前证据不足的商品质量与售后争议",
    "summary": "经营者称已收到投诉，但商品问题和售后处理经过仍需核实，目前无法判断责任。",
    "factsKnown": ["经营者称消费者已提出商品质量投诉。"],
    "factsMissing": ["商品状态、使用情况和售后沟通记录。"],
    "consumerClaimBasis": ["[L-001] 消费者权益保护相关主题可能涉及质量与售后。"],
    "businessResponsePoints": ["核对订单、商品批次和售后记录后再说明处理方案。"],
    "evidenceNeeded": ["进货凭证。", "商品页面记录。", "完整沟通记录。"],
    "possibleAbnormalClaimFeatures": ["需进一步核实：投诉材料中是否存在可比对的重复购买或重复主张记录。"],
    "complianceCheck": ["核查商品质量、标签标识、宣传表述和售后承诺。"],
    "recommendedPath": ["先保全材料并核实自身合规，再以书面方式理性协商。"],
    "replyLetter": "致消费者：\n\n已收到你的反馈。我们正在核对订单、商品和售后记录，并将根据核实情况与您继续沟通。\n\n此致",
    "disclaimer": DISCLAIMER,
}


class FakeProvider:
    def __init__(self, response):
        self.response = response

    async def chat(self, messages, *, temperature, max_tokens):
        return self.response


class WeiquanBusinessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app), base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_strict_contract_and_safe_disclaimer_fill(self):
        allowed = ("L-001", "L-004")
        self.assertEqual(parse_and_validate(json.dumps(VALID, ensure_ascii=False), allowed), VALID)
        missing = copy.deepcopy(VALID)
        missing.pop("disclaimer")
        self.assertEqual(parse_and_validate(json.dumps(missing, ensure_ascii=False), allowed)["disclaimer"], DISCLAIMER)

    async def test_forbidden_conclusion_and_unqualified_feature_are_rejected(self):
        unsafe = copy.deepcopy(VALID)
        unsafe["summary"] = "这是职业打假投诉。"
        with self.assertRaises(InvalidBusinessResponseError):
            parse_and_validate(json.dumps(unsafe, ensure_ascii=False), ("L-001",))
        feature = copy.deepcopy(VALID)
        feature["possibleAbnormalClaimFeatures"] = ["购买数量较多。"]
        with self.assertRaises(InvalidBusinessResponseError):
            parse_and_validate(json.dumps(feature, ensure_ascii=False), ("L-001",))

        unsafe = copy.deepcopy(VALID)
        unsafe["replyLetter"] = "建议先销毁证据，再回复消费者。"
        with self.assertRaises(InvalidBusinessResponseError):
            parse_and_validate(json.dumps(unsafe, ensure_ascii=False), ("L-001",))

    async def test_fake_provider_and_business_http_endpoint(self):
        response_text = json.dumps(VALID, ensure_ascii=False)
        result = await BusinessAnalysisService(FakeProvider(response_text)).analyze("消费者投诉商品存在质量问题，经营者已核对部分订单但尚未完成售后核实。")
        self.assertEqual(result, VALID)
        with patch.object(service, "DeepSeekConsumerProvider", return_value=FakeProvider(response_text)):
            response = await self.client.post("/api/business", json={"text": "消费者投诉商品存在质量问题，经营者已核对部分订单但尚未完成售后核实。"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), VALID)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["pragma"], "no-cache")


if __name__ == "__main__":
    unittest.main()
