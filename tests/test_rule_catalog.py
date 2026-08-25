from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.rule_catalog import (
    build_rule_context,
    load_rule_catalog,
    rule_ids_in_context,
    select_frontend_rules,
    select_rules,
)


class RuleCatalogTest(unittest.TestCase):
    def test_load_and_select_rules(self):
        with TemporaryDirectory() as directory:
            rules_dir = Path(directory)
            (rules_dir / "GEN-001.md").write_text(
                "---\nrule_id: GEN-001\nstatus: 已核验\nindustry: [通用]\nmedium: [详情页]\n---\n",
                encoding="utf-8",
            )
            (rules_dir / "MED-001.md").write_text(
                "---\nrule_id: MED-001\nstatus: 已核验\nindustry:\n  - 医疗健康\nmedium:\n  - 详情页\n---\n",
                encoding="utf-8",
            )

            rules = load_rule_catalog(rules_dir)
            selected = select_rules(rules, "医疗健康", "详情页")

            self.assertEqual([rule.rule_id for rule in selected], ["MED-001", "GEN-001"])

    def test_rejects_missing_directory(self):
        with self.assertRaises(ValueError):
            load_rule_catalog("/missing/rules")

    def test_blank_platform_keeps_industry_rules(self):
        with TemporaryDirectory() as directory:
            rules_dir = Path(directory)
            (rules_dir / "MED-001.md").write_text(
                "---\nrule_id: MED-001\nstatus: 已核验\nindustry: [医疗健康]\nmedium: [详情页]\n---\n",
                encoding="utf-8",
            )

            selected = select_frontend_rules(load_rule_catalog(rules_dir), "medical", "")

            self.assertEqual([rule.rule_id for rule in selected], ["MED-001"])

    def test_frontend_selection_and_context_only_use_verified_rules(self):
        with TemporaryDirectory() as directory:
            rules_dir = Path(directory)
            (rules_dir / "GEN-001.md").write_text(
                "---\nrule_id: GEN-001\nstatus: 已核验\nindustry: [通用]\nmedium: [详情页]\n---\n\n## 规则结论\n\n通用结论。\n",
                encoding="utf-8",
            )
            (rules_dir / "MED-001.md").write_text(
                "---\nrule_id: MED-001\nstatus: 待核验\nindustry: [医疗健康]\nmedium: [详情页]\n---\n\n## 规则结论\n\n不应进入提示词。\n",
                encoding="utf-8",
            )

            selected = select_frontend_rules(load_rule_catalog(rules_dir), "medical", "taobao")

            self.assertEqual([rule.rule_id for rule in selected], ["MED-001", "GEN-001"])
            self.assertEqual(build_rule_context(selected), "- [GEN-001] 通用结论。")

    def test_context_rule_ids_only_include_rendered_rules(self):
        context = "- [GEN-001] 结论\n- [MED-001] 结论"
        self.assertEqual(rule_ids_in_context(context), {"GEN-001", "MED-001"})


if __name__ == "__main__":
    unittest.main()
