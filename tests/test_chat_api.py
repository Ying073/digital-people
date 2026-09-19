import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from app import main
from app.learning import LearningStore


class ChatApiTests(unittest.TestCase):
    def test_teacher_can_review_and_publish_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LearningStore(Path(directory) / "learning.json")
            candidate = store.record_gap("什么是引用？", "模型草稿", top_score=0.0)
            with patch.object(main, "learning_store", store):
                queue = main.admin_learning_candidates("teacher123")
                result = main.approve_learning_candidate(
                    candidate["id"],
                    main.LearningApprovalRequest(answer="引用是变量的别名。"),
                    "teacher123",
                )

            self.assertEqual(queue["pending"], 1)
            self.assertTrue(result["ok"])
            self.assertEqual(store.search_approved("引用")[0]["text"], "引用是变量的别名。")

    def test_approved_answer_is_used_by_later_chat_without_external_model(self) -> None:
        settings = {"base_url": "", "model": "", "api_key": ""}
        voice_settings = {"allow_browser_fallback": False, "volume": 1.0}
        with tempfile.TemporaryDirectory() as directory:
            store = LearningStore(Path(directory) / "learning.json")
            candidate = store.record_gap("什么是引用？", "候选草稿", top_score=0.0)
            store.approve(candidate["id"], "引用是变量的别名，修改引用也会修改原变量。")
            with patch.object(main, "learning_store", store), \
                    patch.object(main.knowledge, "search", return_value=[]), \
                    patch.object(main.voice_library, "list", return_value=[]), \
                    patch.object(main, "read_settings", return_value=settings), \
                    patch.object(main, "read_voice_settings", return_value=voice_settings), \
                    patch.object(main, "audio_response_for", return_value=(None, "none")):
                response = main.chat(main.ChatRequest(message="引用是什么？"))

            self.assertEqual(response["answer"], "引用是变量的别名，修改引用也会修改原变量。")
            self.assertEqual(response["sources"][0]["kind"], "reviewed_learning")
            self.assertFalse(response["knowledge_gap_recorded"])

    def test_missing_knowledge_is_added_to_teacher_review_queue(self) -> None:
        settings = {"base_url": "", "model": "", "api_key": ""}
        voice_settings = {"allow_browser_fallback": False, "volume": 1.0}
        with tempfile.TemporaryDirectory() as directory:
            store = LearningStore(Path(directory) / "learning.json")
            with patch.object(main, "learning_store", store), \
                    patch.object(main.knowledge, "search", return_value=[]), \
                    patch.object(main.voice_library, "list", return_value=[]), \
                    patch.object(main, "read_settings", return_value=settings), \
                    patch.object(main, "read_voice_settings", return_value=voice_settings), \
                    patch.object(main, "audio_response_for", return_value=(None, "none")):
                response = main.chat(main.ChatRequest(message="vector 如何自动扩容？"))

            candidates = store.list_candidates()
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["question"], "vector 如何自动扩容？")
            self.assertEqual(candidates[0]["draft_answer"], response["answer"])
            self.assertTrue(response["knowledge_gap_recorded"])

    def test_strong_knowledge_match_is_not_added_to_review_queue(self) -> None:
        source = {
            "id": "lesson-1", "document_id": "lesson", "filename": "lesson.txt",
            "section": "vector", "text": "vector 是顺序容器。", "position": 1, "score": 3.0,
        }
        settings = {"base_url": "", "model": "", "api_key": ""}
        voice_settings = {"allow_browser_fallback": False, "volume": 1.0}
        with tempfile.TemporaryDirectory() as directory:
            store = LearningStore(Path(directory) / "learning.json")
            with patch.object(main, "learning_store", store), \
                    patch.object(main.knowledge, "search", return_value=[source]), \
                    patch.object(main.voice_library, "list", return_value=[]), \
                    patch.object(main, "read_settings", return_value=settings), \
                    patch.object(main, "read_voice_settings", return_value=voice_settings), \
                    patch.object(main, "audio_response_for", return_value=(None, "none")):
                response = main.chat(main.ChatRequest(message="vector 是什么？"))

            self.assertEqual(store.list_candidates(), [])
            self.assertFalse(response["knowledge_gap_recorded"])
            self.assertEqual(len(response["follow_up_questions"]), 3)
            self.assertEqual(len(set(response["follow_up_questions"])), 3)

    def test_rejected_model_copy_keeps_local_rephrase_mode(self) -> None:
        source_text = (
            "判断一个整数是奇数还是偶数时，可以将这个整数除以二，"
            "如果余数是零，那么它就是偶数，否则它就是奇数。"
        )
        sources = [{
            "id": "lesson-1",
            "document_id": "lesson",
            "filename": "lesson.txt",
            "section": "第7课 整数奇偶判断",
            "text": source_text,
            "position": 1,
            "score": 3.2,
        }]
        model_settings = {
            "base_url": "https://example.test/v1",
            "model": "test-model",
            "api_key": "test-key",
        }
        voice_settings = {
            "allow_browser_fallback": False,
            "volume": 1.0,
        }

        with patch.object(main.knowledge, "search", return_value=sources), \
                patch.object(main.voice_library, "list", return_value=[]), \
                patch.object(main, "read_settings", return_value=model_settings), \
                patch.object(main, "read_voice_settings", return_value=voice_settings), \
                patch.object(main, "chat_completion", side_effect=[source_text, source_text]), \
                patch.object(main, "audio_response_for", return_value=(None, "none")):
            response = main.chat(main.ChatRequest(message="怎样判断奇偶数？"))

        self.assertEqual(response["mode"], "local_rephrase")


if __name__ == "__main__":
    unittest.main()
