import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app import main


class SpeechApiTests(unittest.TestCase):
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
