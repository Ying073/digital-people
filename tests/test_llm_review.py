import unittest

from app.llm import LLMError, parse_learning_review


class LearningReviewParserTests(unittest.TestCase):
    def test_parses_fenced_json_review(self) -> None:
        review = parse_learning_review(
            """```json
            {"decision":"auto_publish","confidence":0.96,"canonical_question":"什么是循环？",\
            "canonical_answer":"循环让一段代码重复执行。","reason":"稳定的基础知识"}
            ```"""
        )

        self.assertEqual(review["decision"], "auto_publish")
        self.assertEqual(review["confidence"], 0.96)

    def test_rejects_unknown_decision(self) -> None:
        with self.assertRaises(LLMError):
            parse_learning_review(
                '{"decision":"maybe","confidence":0.9,"canonical_question":"问题",'
                '"canonical_answer":"答案","reason":"原因"}'
            )

    def test_rejects_non_text_model_content(self) -> None:
        with self.assertRaises(LLMError):
            parse_learning_review([{"type": "text", "text": "not supported"}])


if __name__ == "__main__":
    unittest.main()
