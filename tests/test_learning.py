import tempfile
import unittest
from pathlib import Path

from app.learning import LearningStore, is_learning_candidate


class LearningStoreTests(unittest.TestCase):
    def test_trivial_greetings_are_not_learning_candidates(self) -> None:
        self.assertFalse(is_learning_candidate("你好"))
        self.assertFalse(is_learning_candidate("谢谢老师"))
        self.assertTrue(is_learning_candidate("什么是函数重载？"))

    def test_obvious_contact_details_are_redacted_before_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LearningStore(Path(directory) / "learning.json")
            item = store.record_gap(
                "邮箱 pupil@example.com，手机号 13812345678，怎么学循环？",
                "请联系 pupil@example.com 后学习。",
                top_score=0.0,
            )

            self.assertNotIn("pupil@example.com", item["question"])
            self.assertNotIn("13812345678", item["question"])
            self.assertNotIn("pupil@example.com", item["draft_answer"])

    def test_repeated_question_is_grouped_and_counted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "learning.json"
            store = LearningStore(path)

            first = store.record_gap("什么是 指针？", "第一版草稿", top_score=0.0)
            second = store.record_gap("  什么是指针? ", "更新后的草稿", top_score=0.2)

            self.assertEqual(first["id"], second["id"])
            self.assertEqual(second["occurrences"], 2)
            self.assertEqual(second["draft_answer"], "更新后的草稿")
            self.assertEqual(len(LearningStore(path).list_candidates()), 1)

    def test_approval_publishes_searchable_entry_and_rejection_hides_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LearningStore(Path(directory) / "learning.json")
            approved = store.record_gap("vector 是什么？", "候选草稿", top_score=None)
            rejected = store.record_gap("怎么作弊？", "不应发布", top_score=0.1)

            entry = store.approve(approved["id"], "vector 是可以自动扩容的顺序容器。")
            store.reject(rejected["id"])

            self.assertEqual(store.list_candidates(), [])
            self.assertEqual(entry["status"], "approved")
            results = store.search_approved("vector 容器", limit=3)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["text"], "vector 是可以自动扩容的顺序容器。")
            self.assertEqual(results[0]["source_kind"], "reviewed_learning")

    def test_approval_requires_a_nonempty_teacher_answer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LearningStore(Path(directory) / "learning.json")
            candidate = store.record_gap("什么是递归？", "候选草稿", top_score=0.0)

            with self.assertRaises(ValueError):
                store.approve(candidate["id"], "   ")

    def test_list_approved_returns_only_published_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LearningStore(Path(directory) / "learning.json")
            published = store.record_gap("什么是函数？", "草稿", top_score=0.0)
            store.record_gap("什么是指针？", "草稿", top_score=0.0)
            store.approve(published["id"], "函数是可重复使用的代码块。")

            approved = store.list_approved()

            self.assertEqual(len(approved), 1)
            self.assertEqual(approved[0]["question"], "什么是函数？")
            self.assertEqual(approved[0]["status"], "approved")


if __name__ == "__main__":
    unittest.main()
