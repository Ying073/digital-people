import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from app import main
from app.learning import LearningStore
from app.llm import LLMError


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
            self.assertEqual(response["knowledge_update"], "pending_review")

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
            self.assertEqual(response["knowledge_update"], "not_needed")
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

    def test_safe_simple_gap_is_auto_published_after_model_review(self) -> None:
        model_settings = {
            "base_url": "https://example.test/v1",
            "model": "test-model",
            "api_key": "test-key",
        }
        voice_settings = {"allow_browser_fallback": False, "volume": 1.0}
        review = {
            "decision": "auto_publish",
            "confidence": 0.98,
            "canonical_question": "什么是变量？",
            "canonical_answer": "变量是程序中一个有名字、用来保存数据的位置。",
            "reason": "基础且稳定的编程概念",
        }
        with tempfile.TemporaryDirectory() as directory:
            store = LearningStore(Path(directory) / "learning.json")
            with patch.object(main, "learning_store", store), \
                    patch.object(main.knowledge, "search", return_value=[]), \
                    patch.object(main.voice_library, "list", return_value=[]), \
                    patch.object(main, "read_settings", return_value=model_settings), \
                    patch.object(main, "read_voice_settings", return_value=voice_settings), \
                    patch.object(main, "chat_completion", return_value="变量就像一个有名字的小盒子。"), \
                    patch.object(main, "judge_learning_candidate", return_value=review), \
                    patch.object(main, "audio_response_for", return_value=(None, "none")):
                response = main.chat(main.ChatRequest(message="变量是什么？"))

            self.assertTrue(response["knowledge_gap_recorded"])
            self.assertEqual(response["knowledge_update"], "auto_published")
            self.assertEqual(store.list_candidates(), [])
            self.assertEqual(store.list_approved()[0]["question"], "什么是变量？")
            self.assertTrue(store.list_approved()[0]["auto_published"])

    def test_uncertain_model_review_stays_in_teacher_queue(self) -> None:
        model_settings = {
            "base_url": "https://example.test/v1",
            "model": "test-model",
            "api_key": "test-key",
        }
        voice_settings = {"allow_browser_fallback": False, "volume": 1.0}
        review = {
            "decision": "auto_publish",
            "confidence": 0.65,
            "canonical_question": "学完课程能保证就业吗？",
            "canonical_answer": "学习编程可能帮助培养解决问题的能力。",
            "reason": "涉及个人结果，不能确定",
        }
        with tempfile.TemporaryDirectory() as directory:
            store = LearningStore(Path(directory) / "learning.json")
            with patch.object(main, "learning_store", store), \
                    patch.object(main.knowledge, "search", return_value=[]), \
                    patch.object(main.voice_library, "list", return_value=[]), \
                    patch.object(main, "read_settings", return_value=model_settings), \
                    patch.object(main, "read_voice_settings", return_value=voice_settings), \
                    patch.object(main, "chat_completion", return_value="学习效果因人而异。"), \
                    patch.object(main, "judge_learning_candidate", return_value=review), \
                    patch.object(main, "audio_response_for", return_value=(None, "none")):
                response = main.chat(main.ChatRequest(message="学完课程能保证就业吗？"))

            self.assertEqual(response["knowledge_update"], "pending_review")
            self.assertEqual(len(store.list_candidates()), 1)
            self.assertEqual(store.list_approved(), [])

    def test_model_review_failure_stays_in_teacher_queue(self) -> None:
        model_settings = {
            "base_url": "https://example.test/v1",
            "model": "test-model",
            "api_key": "test-key",
        }
        voice_settings = {"allow_browser_fallback": False, "volume": 1.0}
        with tempfile.TemporaryDirectory() as directory:
            store = LearningStore(Path(directory) / "learning.json")
            with patch.object(main, "learning_store", store), \
                    patch.object(main.knowledge, "search", return_value=[]), \
                    patch.object(main.voice_library, "list", return_value=[]), \
                    patch.object(main, "read_settings", return_value=model_settings), \
                    patch.object(main, "read_voice_settings", return_value=voice_settings), \
                    patch.object(main, "chat_completion", return_value="变量可以保存数据。"), \
                    patch.object(main, "judge_learning_candidate", side_effect=LLMError("invalid json")), \
                    patch.object(main, "audio_response_for", return_value=(None, "none")):
                response = main.chat(main.ChatRequest(message="变量是什么？"))

            self.assertEqual(response["knowledge_update"], "pending_review")
            self.assertEqual(len(store.list_candidates()), 1)


if __name__ == "__main__":
    unittest.main()
