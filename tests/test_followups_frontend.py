import unittest
from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


class FollowUpFrontendTests(unittest.TestCase):
    def test_answer_renders_three_clickable_follow_up_questions(self) -> None:
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")

        self.assertIn("function addFollowUpQuestions(", script)
        self.assertIn("payload.follow_up_questions", script)
        self.assertIn('className = "follow-up-questions"', script)
        self.assertIn('className = "follow-up-question"', script)
        self.assertIn('button.addEventListener("click", () => ask(question))', script)
        self.assertIn(".follow-up-questions", css)
        self.assertIn(".follow-up-question", css)


if __name__ == "__main__":
    unittest.main()
