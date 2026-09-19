import unittest
from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


class KnowledgeMapFrontendTests(unittest.TestCase):
    def test_sidebar_is_rendered_from_the_dynamic_map(self) -> None:
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        script = (STATIC / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="knowledgeMap"', html)
        self.assertNotIn('class="lesson active"', html)
        self.assertIn('fetch("/api/knowledge-map")', script)
        self.assertIn("function renderKnowledgeMap(", script)
        self.assertIn("function highlightKnowledgeTopic(", script)
        self.assertIn('className = "knowledge-topic"', script)

    def test_map_displays_point_counts_and_expandable_modules(self) -> None:
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")

        self.assertIn("个知识点", script)
        self.assertIn('document.createElement("details")', script)
        self.assertIn('document.createElement("summary")', script)
        self.assertIn(".knowledge-module", css)
        self.assertIn(".knowledge-topic.active", css)


if __name__ == "__main__":
    unittest.main()
