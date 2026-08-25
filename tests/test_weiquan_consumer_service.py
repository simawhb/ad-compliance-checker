import copy
import json
import sys
import unittest
from collections import deque
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import httpx  # noqa: E402
import weiquan_consumer_service as service  # noqa: E402


SAMPLES = json.loads((ROOT / "tests" / "fixtures" / "weiquan_consumer_response_samples.json").read_text(encoding="utf-8"))


class FakeProvider:
    def __init__(self, response):
        self.response = response

    async def chat(self, messages, *, temperature, max_tokens):
        return self.response


class FailingProvider:
    async def chat(self, messages, *, temperature, max_tokens):
        raise RuntimeError("provider unavailable")


class WeiquanConsumerServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        service._request_times = deque()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app), base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_success_has_only_contract_data_and_no_store(self):
        response_text = json.dumps(SAMPLES["valid"], ensure_ascii=False)
        with patch.object(service, "DeepSeekConsumerProvider", return_value=FakeProvider(response_text)):
            response = await self.client.post("/api/consumer", json={"text": "网上购买商品后发现质量问题，商家售后一直没有明确回复。"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), SAMPLES["valid"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["pragma"], "no-cache")

    async def test_invalid_input_does_not_echo_body(self):
        body = "短文本"
        response = await self.client.post("/api/consumer", json={"text": body})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(body, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    async def test_invalid_provider_response_is_not_relayed(self):
        raw = "```json\\n{\\\"secret\\\":\\\"do-not-relay\\\"}\\n```"
        with patch.object(service, "DeepSeekConsumerProvider", return_value=FakeProvider(raw)):
            response = await self.client.post("/api/consumer", json={"text": "网上购买商品后发现质量问题，商家售后一直没有明确回复。"})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("do-not-relay", response.text)
        self.assertIn("X-Request-ID", response.headers)

    async def test_provider_failure_uses_safe_response(self):
        with patch.object(service, "DeepSeekConsumerProvider", return_value=FailingProvider()):
            response = await self.client.post("/api/consumer", json={"text": "网上购买商品后发现质量问题，商家售后一直没有明确回复。"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("provider unavailable", response.text)

    async def test_unknown_request_fields_are_rejected(self):
        payload = {"text": "网上购买商品后发现质量问题，商家售后一直没有明确回复。", "caseId": "must-not-exist"}
        response = await self.client.post("/api/consumer", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("caseId", response.text)

    async def test_consumer_provider_requests_json_object_mode(self):
        class FakeClient:
            async def chat(self, messages, *, temperature, max_tokens, response_format=None):
                self.messages = messages
                self.temperature = temperature
                self.max_tokens = max_tokens
                self.response_format = response_format
                return "{}"

        fake_client = FakeClient()
        with patch.object(service, "LLMClient", return_value=fake_client):
            provider = service.DeepSeekConsumerProvider()
            self.assertEqual(await provider.chat([{"role": "user", "content": "test"}], temperature=0.1, max_tokens=8192), "{}")
        self.assertEqual(fake_client.response_format, {"type": "json_object"})

    async def test_provider_diagnostic_log_contains_no_case_text(self):
        sensitive_fixture = "虚构案件正文不得写入日志"
        with patch.object(service.logger, "warning") as warning:
            service._log_provider_outcome(
                "consumer",
                503,
                0.0,
                service.ProviderUnavailableError(sensitive_fixture),
            )
        rendered = " ".join(str(part) for call in warning.call_args_list for part in call.args)
        self.assertNotIn(sensitive_fixture, rendered)
        self.assertIn("endpoint=%s", warning.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
