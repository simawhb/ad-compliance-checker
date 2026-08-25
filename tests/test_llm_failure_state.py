import asyncio
import sys
import types
import unittest
from pathlib import Path

try:
    import httpx  # noqa: F401
except ModuleNotFoundError:
    sys.modules.setdefault("httpx", types.SimpleNamespace())
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import llm
from llm import (
    LLMClient,
    ReviewIncompleteError,
    _normalized_missing_materials,
    _parse_llm_response,
    _safe_suggestion,
    review_ad_copy,
)


class LLMFailureStateTest(unittest.TestCase):
    def test_missing_model_configuration_is_incomplete(self):
        client = LLMClient(api_key="configured-for-test")
        client.api_key = ""

        with self.assertRaises(ReviewIncompleteError):
            asyncio.run(client.chat([{"role": "user", "content": "test"}]))

    def test_invalid_model_json_is_incomplete(self):
        secret = "synthetic-model-output-must-not-enter-log"
        with self.assertLogs("llm", level="ERROR") as captured:
            with self.assertRaises(ReviewIncompleteError):
                _parse_llm_response(secret)
        self.assertNotIn(secret, "\n".join(captured.output))

    def test_provider_exception_text_is_not_logged(self):
        secret = "synthetic-case-body-must-not-enter-log"

        class FailingAsyncClient:
            def __init__(self, **_):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return False

            async def post(self, *_args, **_kwargs):
                raise RuntimeError(secret)

        original = llm.httpx.AsyncClient
        llm.httpx.AsyncClient = FailingAsyncClient
        try:
            with self.assertLogs("llm", level="ERROR") as captured:
                with self.assertRaises(RuntimeError):
                    asyncio.run(LLMClient(api_key="configured-for-test").chat([{"role": "user", "content": "test"}]))
        finally:
            llm.httpx.AsyncClient = original

        output = "\n".join(captured.output)
        self.assertIn("RuntimeError", output)
        self.assertNotIn(secret, output)

    def test_review_passes_verified_rule_context_to_model(self):
        class FakeClient:
            messages = []

            async def chat(self, messages):
                self.messages = messages
                return '{"summary":"完成","risk_level":"中风险","missing_materials":["销量数据来源"],"violations":[{"dimension":"极限词审查","content":"最好","severity":"中等","law_basis":"广告法","suggestion":"删除","rule_ids":["GEN-ABS-001"]}]}'

        previous_client = llm._client
        fake_client = FakeClient()
        llm._client = fake_client
        try:
            result = asyncio.run(review_ad_copy(
                "测试文案", "- [GEN-001] 已核验结论", {"GEN-001"}
            ))
        finally:
            llm._client = previous_client

        self.assertIn("[GEN-001] 已核验结论", fake_client.messages[1]["content"])
        self.assertEqual(result.violation_items[0].rule_ids, [])
        self.assertEqual(result.missing_materials, ["销量数据来源"])

    def test_missing_materials_are_bounded_and_deduplicated(self):
        materials = _normalized_missing_materials(
            ["  检测 报告  ", "检测 报告", 123, "x" * 300] + ["额外材料"] * 10
        )

        self.assertEqual(materials[0], "检测 报告")
        self.assertEqual(len(materials[1]), 200)
        self.assertLessEqual(len(materials), 10)

    def test_medical_suggestion_does_not_create_new_unverified_claim(self):
        suggestion = _safe_suggestion(
            "保证治愈所有疾病",
            "将治愈改为辅助改善",
        )

        self.assertNotIn("辅助改善", suggestion)
        self.assertIn("删除", suggestion)
        self.assertIn("批准内容", suggestion)

    def test_price_comparison_requires_evidence_instead_of_synonym(self):
        suggestion = _safe_suggestion(
            "全网最低",
            "改为优惠价",
        )

        self.assertIn("删除", suggestion)
        self.assertIn("价格依据", suggestion)


if __name__ == "__main__":
    unittest.main()
