import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import main
from schemas import PlatformEnum, ReviewResult, RiskLevel


class ResultRetentionTest(unittest.TestCase):
    def setUp(self):
        main._review_results.clear()

    def tearDown(self):
        main._review_results.clear()

    def test_result_is_not_stored_by_default(self):
        result = ReviewResult(
            id="TEST-NO-STORE",
            channel="upload",
            platform=PlatformEnum.MANUAL,
            risk_level=RiskLevel.LOW,
        )

        with patch.object(main, "_RESULT_RETENTION_ENABLED", False):
            main._store_review_result(result)
            response = main._as_web_review_response(result)

        self.assertEqual(main._review_results, {})
        self.assertFalse(response["retained"])
        self.assertEqual(response["result_id"], "")
        self.assertEqual(response["risk_level"], "低风险")
        self.assertIn("不代表广告已经获得合规确认", response["conclusion_notice"])

    def test_explicit_retention_stores_result(self):
        result = ReviewResult(
            id="TEST-STORE",
            channel="upload",
            platform=PlatformEnum.MANUAL,
            risk_level=RiskLevel.MEDIUM,
        )

        with patch.object(main, "_RESULT_RETENTION_ENABLED", True):
            main._store_review_result(result)
            response = main._as_web_review_response(result)

        self.assertIs(main._review_results["TEST-STORE"], result)
        self.assertTrue(response["retained"])
        self.assertEqual(response["result_id"], "TEST-STORE")


if __name__ == "__main__":
    unittest.main()
