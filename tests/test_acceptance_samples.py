import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import main


class AcceptanceSamplesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = ROOT / "tests" / "fixtures" / "acceptance_cases.json"
        cls.cases = json.loads(fixture.read_text(encoding="utf-8"))

    def test_first_batch_has_two_medical_and_two_ecommerce_cases(self):
        industries = [case["industry"] for case in self.cases]
        self.assertEqual(industries.count("medical"), 2)
        self.assertEqual(industries.count("ecommerce"), 2)

    def test_cases_are_synthetic_and_contain_required_fields(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["product_name"].startswith("示例"))
                for field in (
                    "medium",
                    "product_type",
                    "verified_facts",
                    "desired_message",
                    "proof_materials",
                ):
                    self.assertTrue(case[field].strip())
                self.assertNotIn("@", json.dumps(case, ensure_ascii=False))
                self.assertNotRegex(
                    json.dumps(case, ensure_ascii=False),
                    r"1[3-9]\d{9}",
                )

    def test_complete_cases_pass_deterministic_material_preflight(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                missing = main._draft_required_materials(
                    case["industry"],
                    case["details"],
                    case["desired_message"],
                )
                self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
