import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app import main


class SpeechApiTests(unittest.TestCase):
    def test_teacher_can_check_gpt_sovits_service_status(self):
        settings = {"service_url": "http://127.0.0.1:9880"}
        expected = {"running": True, "detail": ""}
        with patch.object(main, "read_voice_settings", return_value=settings), \
                patch.object(main, "gpt_sovits_status", return_value=expected) as probe:
            result = main.voice_service_status("teacher123")

        self.assertEqual(result, {**expected, "service_url": settings["service_url"]})
        probe.assert_called_once_with(settings["service_url"])

    def test_voice_service_status_requires_teacher_password(self):
        with self.assertRaises(HTTPException) as raised:
            main.voice_service_status("wrong-password")
        self.assertEqual(raised.exception.status_code, 401)

    def test_system_speech_returns_a_replayable_audio_url(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(main, "TTS_CACHE", Path(directory)), \
                patch.object(main, "sys", SimpleNamespace(platform="win32")), \
                patch.object(main, "read_voice_settings", return_value={"allow_browser_fallback": True, "speed": 1.0}), \
                patch.object(main, "synthesize_windows_sapi", return_value=b"RIFF" + b"0" * 80) as synthesize:
            result = main.speech_audio(main.SpeechRequest(text="变量是什么？"))
            audio_id = result["audio_url"].rsplit("/", 1)[-1]
            self.assertEqual((Path(directory) / f"{audio_id}.wav").read_bytes(), b"RIFF" + b"0" * 80)
            synthesize.assert_called_once_with("变量是什么？", speed=1.0)

    def test_disabled_fallback_does_not_synthesize(self):
        with patch.object(main, "sys", SimpleNamespace(platform="win32")), \
                patch.object(main, "read_voice_settings", return_value={"allow_browser_fallback": False}):
            with self.assertRaises(HTTPException) as raised:
                main.speech_audio(main.SpeechRequest(text="测试"))
            self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
