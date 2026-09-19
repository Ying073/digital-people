import unittest

from app.followups import suggest_follow_up_questions


class FollowUpQuestionTests(unittest.TestCase):
    def test_loop_question_gets_three_deeper_loop_prompts(self) -> None:
        suggestions = suggest_follow_up_questions(
            "for 循环怎样计算1到10的和？",
            "可以用 for 循环不断累加。",
            [{"section": "第9课 高斯求和计算"}],
        )

        self.assertEqual(len(suggestions), 3)
        self.assertEqual(len(set(suggestions)), 3)
        self.assertTrue(any("for" in item and "while" in item for item in suggestions))
        self.assertTrue(any("练习" in item for item in suggestions))

    def test_learning_plan_question_gets_actionable_next_steps(self) -> None:
        suggestions = suggest_follow_up_questions(
            "零基础学 C++ 应该怎么规划？",
            "先从输出和变量开始。",
            [{"section": "2.7 中小学生如何制定适合自己的自学C++编程规划？"}],
        )

        self.assertEqual(len(suggestions), 3)
        self.assertTrue(any("第一周" in item for item in suggestions))
        self.assertTrue(any("掌握" in item for item in suggestions))

    def test_generic_prompts_use_the_retrieved_topic_and_stay_compact(self) -> None:
        suggestions = suggest_follow_up_questions(
            "请讲讲这一课",
            "这是一个基础知识点。",
            [{"section": "第3课 文具购买总花费计算"}],
        )

        self.assertEqual(len(suggestions), 3)
        self.assertTrue(all(len(item) <= 40 for item in suggestions))
        self.assertTrue(any("文具购买总花费计算" in item for item in suggestions))


if __name__ == "__main__":
    unittest.main()
