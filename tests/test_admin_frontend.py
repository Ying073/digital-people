import unittest
from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


class AdminFrontendTests(unittest.TestCase):
    def test_admin_shows_gpt_sovits_runtime_status_and_start_command(self) -> None:
        html = (STATIC / "admin.html").read_text(encoding="utf-8")
        script = (STATIC / "admin.js").read_text(encoding="utf-8")

        self.assertIn('id="voiceServiceStatus"', html)
        self.assertIn("scripts/start-gpt-sovits.ps1 -Background", html)
        self.assertIn("/api/admin/voice-service-status", script)
        self.assertIn("服务已运行", script)
        self.assertIn("服务未启动", script)
        self.assertNotIn("373b79c0561c4c3c952fffd9e3a65c09", html + script)

    def test_admin_has_review_queue_and_versioned_assets(self) -> None:
        html = (STATIC / "admin.html").read_text(encoding="utf-8")

        self.assertIn('id="learningQueue"', html)
        self.assertIn('id="learningStats"', html)
        self.assertIn("知识缺口审核", html)
        self.assertIn("审核通过后", html)
        self.assertRegex(html, r'href="/admin\.css\?v=[^"]+"')
        self.assertRegex(html, r'src="/admin\.js\?v=[^"]+"')

    def test_admin_script_supports_edit_approve_and_reject(self) -> None:
        script = (STATIC / "admin.js").read_text(encoding="utf-8")

        self.assertIn("async function loadLearningCandidates()", script)
        self.assertIn("/api/admin/learning-candidates", script)
        self.assertIn("/approve", script)
        self.assertIn("/reject", script)
        self.assertIn('document.createElement("textarea")', script)


if __name__ == "__main__":
    unittest.main()
