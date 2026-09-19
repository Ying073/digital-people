import unittest
from dataclasses import asdict
from unittest.mock import patch

from app import main
from app.knowledge import Chunk
from app.knowledge_map import build_knowledge_map


def chunk(section: str, text: str, filename: str = "小学编程教材.docx", position: int = 1) -> Chunk:
    return Chunk(
        id=f"chunk-{position}",
        document_id="document-1",
        filename=filename,
        section=section,
        text=text,
        position=position,
    )


class KnowledgeMapTests(unittest.TestCase):
    def test_map_keeps_teaching_order_and_groups_repeated_sections(self) -> None:
        result = build_knowledge_map([
            chunk("第1课 编程入门欢迎语输出", "cout 输出文字。", position=1),
            chunk("第1课 编程入门欢迎语输出", "程序包含 main 函数。", position=2),
            chunk("第7课 整数奇偶判断", "用 if 判断余数。", position=3),
            chunk("第9课 高斯求和计算", "用 for 循环累加。", position=4),
        ])

        self.assertEqual(result["total_points"], 4)
        self.assertEqual(
            [module["id"] for module in result["modules"][:6]],
            ["learning-value", "learning-preparation", "learning-methods", "cpp-foundations", "conditionals", "loops"],
        )
        foundations = next(module for module in result["modules"] if module["id"] == "cpp-foundations")
        self.assertEqual(foundations["count"], 2)
        self.assertEqual(len(foundations["items"]), 1)
        self.assertEqual(foundations["items"][0]["chunk_count"], 2)

    def test_imported_qa_and_student_cases_are_supporting_branches(self) -> None:
        result = build_knowledge_map([
            chunk("十五、零基础能否学习", "可以从基础开始。", "zerocode课程问答.md", 1),
            chunk("二、零基础也可以从慢速积累开始", "学员公开经历。", "zerocode学员心得案例.md", 2),
        ])

        course_faq = next(module for module in result["modules"] if module["id"] == "course-faq")
        learner_cases = next(module for module in result["modules"] if module["id"] == "learner-cases")
        self.assertEqual(course_faq["count"], 1)
        self.assertEqual(learner_cases["count"], 1)
        self.assertEqual(course_faq["items"][0]["source_kind"], "document")

    def test_teacher_approved_knowledge_is_included_and_classified(self) -> None:
        approved = [{
            "id": "approved-1",
            "question": "vector 是什么？",
            "answer": "vector 是可以自动扩容的顺序容器。",
            "status": "approved",
        }]

        result = build_knowledge_map([], approved)

        foundations = next(module for module in result["modules"] if module["id"] == "cpp-foundations")
        self.assertEqual(result["total_points"], 1)
        self.assertEqual(foundations["items"][0]["title"], "vector 是什么？")
        self.assertEqual(foundations["items"][0]["source_kind"], "reviewed_learning")

    def test_textbook_front_matter_and_numbered_guidance_do_not_fall_into_review(self) -> None:
        result = build_knowledge_map([
            chunk("文档开头", "小学 C++ 编程教材说明。", position=1),
            chunk("2.2 中小学学编程与大学生学编程的差异是什么？", "学习目标和节奏不同。", position=2),
        ])

        module_counts = {module["id"]: module["count"] for module in result["modules"]}
        self.assertEqual(module_counts["learning-value"], 1)
        self.assertEqual(module_counts["learning-preparation"], 1)
        self.assertNotIn("to-organize", module_counts)
        value_module = next(module for module in result["modules"] if module["id"] == "learning-value")
        self.assertEqual(value_module["items"][0]["title"], "教材概览")
        self.assertEqual(value_module["items"][0]["section"], "文档开头")

    def test_public_endpoint_uses_current_chunks_and_approved_entries(self) -> None:
        chunks = [chunk("第8课 两个数比大小", "if else 条件判断。")]
        approved = [{"id": "a1", "question": "如何调试？", "answer": "先读报错。", "status": "approved"}]
        with patch.object(main.knowledge, "chunks", chunks), \
                patch.object(main.learning_store, "list_approved", return_value=approved):
            result = main.knowledge_map()

        self.assertEqual(result["total_points"], 2)
        self.assertEqual(sum(module["count"] for module in result["modules"]), 2)


if __name__ == "__main__":
    unittest.main()
