import copy
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "weiquan_consumer_response.schema.json"
SAMPLES_PATH = ROOT / "tests" / "fixtures" / "weiquan_consumer_response_samples.json"
CASES_PATH = ROOT / "tests" / "fixtures" / "weiquan_consumer_cases.json"
DISCLAIMER = "以上内容仅供参考，不构成法律意见，具体以有权机关认定为准。"
REQUIRED = ("disputeType", "summary", "factsKnown", "factsMissing", "legalBasis", "recommendedPath", "evidenceNeeded", "specialNotes", "letter", "disclaimer")
ARRAY_FIELDS = ("factsKnown", "factsMissing", "legalBasis", "recommendedPath", "evidenceNeeded", "specialNotes")


def validate_response(value):
    """Stage 3 lightweight validator; Stage 4 must use an equivalent strict server validator."""
    if not isinstance(value, dict):
        return ["response must be a JSON object"]
    errors = []
    if set(value) != set(REQUIRED):
        errors.append("required fields or additional fields mismatch")
    for field in ("disputeType", "summary", "letter", "disclaimer"):
        if not isinstance(value.get(field), str) or not value.get(field):
            errors.append(f"{field} must be a non-empty string")
    for field in ARRAY_FIELDS:
        items = value.get(field)
        if not isinstance(items, list) or any(not isinstance(item, str) or not item for item in items):
            errors.append(f"{field} must be an array of non-empty strings")
    if isinstance(value.get("letter"), str) and len(value["letter"]) > 3000:
        errors.append("letter exceeds maximum length")
    if isinstance(value.get("disclaimer"), str) and value["disclaimer"] != DISCLAIMER:
        errors.append("disclaimer must equal the standard text")
    for item in value.get("legalBasis", []):
        if not item.startswith("[L-"):
            errors.append("legalBasis item must start with a controlled source ID")
    return errors


class WeiquanConsumerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.samples = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
        cls.cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    def test_schema_contract(self):
        self.assertEqual(self.schema["required"], list(REQUIRED))
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(self.schema["properties"]["disclaimer"]["const"], DISCLAIMER)
        self.assertEqual(self.schema["properties"]["letter"]["maxLength"], 3000)

    def test_valid_fixture(self):
        self.assertEqual(validate_response(self.samples["valid"]), [])

    def test_invalid_fixtures(self):
        invalid = self.samples["invalid"]
        self.assertTrue(validate_response(invalid["missingRequired"]))
        self.assertTrue(validate_response(invalid["wrongType"]))
        self.assertTrue(validate_response(invalid["emptyString"]))
        self.assertTrue(validate_response(invalid["extraMarkdown"]))
        overlong = copy.deepcopy(self.samples["valid"])
        overlong[invalid["overlongField"]["field"]] = "x" * invalid["overlongField"]["length"]
        self.assertTrue(validate_response(overlong))

    def test_evaluation_coverage(self):
        cases = self.cases["cases"]
        identifiers = {case["id"] for case in cases}
        self.assertTrue({f"C{number:02d}" for number in range(1, 21)}.issubset(identifiers))
        for case in cases:
            self.assertTrue(case["expectedBehaviors"])
            self.assertTrue(case["forbiddenBehaviors"])
        self.assertEqual(self.cases["allowedScores"], ["PASS", "FAIL", "REVIEW"])


if __name__ == "__main__":
    unittest.main()
