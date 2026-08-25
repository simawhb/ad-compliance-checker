import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORTAL = ROOT.parent / "enterprise-trial-rollout" / "portal" / "weiquan"
DISCLAIMER = "本工具为个人非经营性信息辅助工具，输出仅供参考，不构成法律意见或服务承诺。"


class WeiquanStaticShellTests(unittest.TestCase):
    def test_all_routes_and_shared_assets_exist(self):
        for path in (
            PORTAL / "index.html",
            PORTAL / "consumer" / "index.html",
            PORTAL / "business" / "index.html",
            PORTAL / "assets" / "weiquan.css",
            PORTAL / "assets" / "weiquan.js",
            PORTAL / "assets" / "favicon.svg",
        ):
            self.assertTrue(path.is_file(), path)

    def test_role_page_links_to_only_the_two_frozen_tools(self):
        page = (PORTAL / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/weiquan/consumer/"', page)
        self.assertIn('href="/weiquan/business/"', page)
        self.assertIn('name="viewport"', page)
        self.assertIn('aria-label="隐私提示"', page)
        self.assertIn(DISCLAIMER, page)

    def test_input_pages_keep_accessible_input_and_disclaimers(self):
        for mode in ("consumer", "business"):
            page = (PORTAL / mode / "index.html").read_text(encoding="utf-8")
            self.assertIn(f'<body data-mode="{mode}">', page)
            self.assertIn('name="viewport"', page)
            self.assertIn('<label for="case-text">', page)
            self.assertIn('aria-describedby="input-help"', page)
            self.assertIn('role="status" aria-live="polite"', page)
            self.assertIn('id="result" class="result-area" aria-live="polite" hidden', page)
            self.assertIn('src="../assets/weiquan.js"', page)
            self.assertIn(DISCLAIMER, page)

    def test_script_uses_only_frozen_same_origin_endpoints_and_no_case_storage(self):
        script = (PORTAL / "assets" / "weiquan.js").read_text(encoding="utf-8")
        self.assertIn("'/weiquan/api/consumer'", script)
        self.assertIn("'/weiquan/api/business'", script)
        self.assertIn("method:'POST'", script)
        self.assertIn("cache:'no-store'", script)
        self.assertIn("credentials:'same-origin'", script)
        for forbidden in ("localStorage", "sessionStorage", "indexedDB", "document.cookie", "DEEPSEEK_API_KEY"):
            self.assertNotIn(forbidden, script)

    def test_shared_css_preserves_mobile_and_accessibility_baseline(self):
        css = (PORTAL / "assets" / "weiquan.css").read_text(encoding="utf-8")
        for required in (
            "min-height:44px",  # touch target baseline
            "overflow-wrap:anywhere",  # long Chinese letter text
            ".button:focus-visible,textarea:focus-visible,input:focus-visible,a:focus-visible",
            "@media(max-width:640px)",
            "grid-template-columns:1fr",  # mobile single-column fallback
            "@media(prefers-reduced-motion:reduce)",
        ):
            self.assertIn(required, css)


if __name__ == "__main__":
    unittest.main()
