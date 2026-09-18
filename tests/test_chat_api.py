import unittest
from unittest.mock import patch

from app import main


class ChatApiTests(unittest.TestCase):
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
