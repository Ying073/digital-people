import unittest

from app.learning_policy import auto_publish_allowed


class LearningPolicyTests(unittest.TestCase):
    def test_high_confidence_simple_programming_knowledge_is_allowed(self) -> None:
        review = {
            "decision": "auto_publish",
            "confidence": 0.97,
            "canonical_question": "什么是变量？",
            "canonical_answer": "变量是程序中一个有名字、用来保存数据的位置。",
            "reason": "基础且稳定的编程概念",
        }

        self.assertTrue(auto_publish_allowed("变量是什么？", review))

    def test_low_confidence_review_requires_manual_review(self) -> None:
        review = {
            "decision": "auto_publish",
            "confidence": 0.78,
            "canonical_question": "什么是变量？",
            "canonical_answer": "变量是用来保存数据的位置。",
            "reason": "答案可能还需要补充",
        }

        self.assertFalse(auto_publish_allowed("变量是什么？", review))

    def test_uncertain_or_course_commitment_content_requires_manual_review(self) -> None:
        uncertain = {
            "decision": "auto_publish",
            "confidence": 0.99,
            "canonical_question": "学完课程能保证就业吗？",
            "canonical_answer": "学完课程保证可以就业。",
            "reason": "积极回答",
        }

        self.assertFalse(auto_publish_allowed("学完课程能保证就业吗？", uncertain))

    def test_sensitive_content_requires_manual_review(self) -> None:
        review = {
            "decision": "auto_publish",
            "confidence": 0.99,
            "canonical_question": "请记住我的手机号 13812345678",
            "canonical_answer": "已经记住你的联系方式。",
            "reason": "用户要求",
        }

        self.assertFalse(auto_publish_allowed("请记住我的手机号 13812345678", review))

    def test_programming_terms_are_not_mistaken_for_personal_promises(self) -> None:
        review = {
            "decision": "auto_publish",
            "confidence": 0.98,
            "canonical_question": "怎样保证数组下标不越界？",
            "canonical_answer": "访问数组前，要让下标保持在零到长度减一之间。",
            "reason": "稳定的编程安全知识",
        }

        self.assertTrue(auto_publish_allowed("怎样保证数组下标不越界？", review))


if __name__ == "__main__":
    unittest.main()
