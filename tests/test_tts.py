import tempfile
import unittest
import json
from unittest.mock import patch
from pathlib import Path

from app.tts import TTSServiceError, VoiceLibrary, strip_for_speech, synthesize_windows_sapi


class VoiceLibraryTests(unittest.TestCase):
    def test_voice_sample_is_whitelisted_by_id(self):
        with tempfile.TemporaryDirectory() as directory:
            library = VoiceLibrary(Path(directory))
            sample = library.add("teacher.wav", b"RIFF" + b"0" * 80, "你好，我是老师。", "encourage")
            self.assertEqual(library.get(sample["id"])["filename"], sample["filename"])
            self.assertIsNone(library.get("C:\\not-allowed.wav"))

    def test_voice_extension_and_consent_boundaries_are_in_service_layer(self):
        with tempfile.TemporaryDirectory() as directory:
            library = VoiceLibrary(Path(directory))
            with self.assertRaises(TTSServiceError):
                library.add("teacher.exe", b"bad", "text", "neutral")

    def test_voice_sample_list_preserves_source_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            library = VoiceLibrary(Path(directory))
            library.manifest_path.write_text(json.dumps([{
                "id": "sample-id",
                "filename": "teacher.wav",
                "transcript": "各位同学大家好。",
                "style": "explain",
                "created_at": "2026-09-15T09:03:27",
                "source_url": "https://example.com/video",
                "source_title": "课程介绍",
                "clip_start_seconds": 30,
                "clip_end_seconds": 47,
            }]), encoding="utf-8")

            sample = library.list()[0]
            self.assertEqual(sample["source_url"], "https://example.com/video")
            self.assertEqual(sample["clip_start_seconds"], 30)

    def test_strip_for_speech_removes_code_fences(self):
        text = strip_for_speech("先看这里：```cpp\ncout << 1;\n```然后解释结果")
        self.assertNotIn("cout", text)
        self.assertIn("代码示例请看黑板", text)

    def test_system_voice_receives_cleaned_text_and_returns_wav(self):
        def render(command, *, env, **kwargs):
            self.assertEqual(env["XIXI_SPEECH_TEXT"], "先看这里：代码示例请看黑板。")
            self.assertEqual(env["XIXI_SPEECH_RATE"], "0")
            Path(env["XIXI_SPEECH_FILE"]).write_bytes(b"RIFF" + b"0" * 80)
            return type("Result", (), {"returncode": 0})()

        with patch("app.tts.subprocess.run", side_effect=render):
            audio = synthesize_windows_sapi("先看这里：```cpp\ncout << 1;\n```")
        self.assertTrue(audio.startswith(b"RIFF"))

    def test_system_voice_failure_is_reported(self):
        with patch("app.tts.subprocess.run", return_value=type("Result", (), {"returncode": 1})()):
            with self.assertRaises(TTSServiceError):
                synthesize_windows_sapi("测试")


if __name__ == "__main__":
    unittest.main()
