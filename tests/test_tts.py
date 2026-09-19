import tempfile
import unittest
import json
import urllib.error
import urllib.parse
from unittest.mock import patch
from pathlib import Path

from app.tts import (
    TTSServiceError,
    VoiceLibrary,
    gpt_sovits_status,
    naturalize_speech_text,
    strip_for_speech,
    synthesize_gpt_sovits,
    synthesize_windows_sapi,
)


ROOT = Path(__file__).resolve().parents[1]


class VoiceLibraryTests(unittest.TestCase):
    def test_gpt_sovits_status_uses_docs_probe(self):
        class Response:
            status = 200

            def __enter__(self): return self
            def __exit__(self, *_): return False

        with patch("app.tts.urllib.request.urlopen", return_value=Response()) as request:
            status = gpt_sovits_status("http://127.0.0.1:9880", timeout=1.5)

        self.assertTrue(status["running"])
        request.assert_called_once_with("http://127.0.0.1:9880/docs", timeout=1.5)

    def test_gpt_sovits_status_reports_connection_failure(self):
        with patch("app.tts.urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            status = gpt_sovits_status("http://127.0.0.1:9880")

        self.assertFalse(status["running"])
        self.assertIn("offline", status["detail"])

    def test_gpt_sovits_scripts_keep_runtime_local_and_reproducible(self):
        setup = ROOT / "scripts" / "setup-gpt-sovits.ps1"
        start = ROOT / "scripts" / "start-gpt-sovits.ps1"

        self.assertTrue(setup.is_file())
        self.assertTrue(start.is_file())
        setup_text = setup.read_text(encoding="utf-8")
        start_text = start.read_text(encoding="utf-8")
        self.assertIn("CU128", setup_text)
        self.assertIn("ModelScope", setup_text)
        self.assertIn("torch==2.7.1+cu128", setup_text)
        self.assertIn("torchaudio==2.7.1+cu128", setup_text)
        self.assertIn("requirements.codex-zh.txt", setup_text)
        self.assertIn("Skipping Open JTalk", setup_text)
        self.assertIn("opencc-python-reimplemented", setup_text)
        self.assertIn("import jieba as jieba_fast", setup_text)
        self.assertIn("127.0.0.1", start_text)
        self.assertIn("9880", start_text)
        for private_value in ("373b79c0561c4c3c952fffd9e3a65c09", "各位同学"):
            self.assertNotIn(private_value, setup_text + start_text)

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

    def test_naturalize_speech_text_turns_layout_into_spoken_pauses(self):
        text = "# 变量\n- 变量像一个小盒子\n- 先起名字"

        self.assertEqual(
            naturalize_speech_text(text),
            "变量。变量像一个小盒子。先起名字。",
        )

    def test_gpt_sovits_request_uses_natural_teacher_preset(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return b"RIFF" + b"0" * 80

        with patch("app.tts.urllib.request.urlopen", return_value=Response()) as request:
            audio = synthesize_gpt_sovits(
                text="# 判断\n- 先看条件\n- 再选分支",
                service_url="http://127.0.0.1:9880",
                sample_path=Path("teacher.wav"),
                prompt_text="各位同学，大家好。",
                speed=0.94,
            )

        query = urllib.parse.parse_qs(urllib.parse.urlparse(request.call_args.args[0]).query)
        self.assertTrue(audio.startswith(b"RIFF"))
        self.assertEqual(query["text"], ["判断。先看条件。再选分支。"])
        self.assertEqual(query["speed_factor"], ["0.94"])
        self.assertEqual(query["top_k"], ["15"])
        self.assertEqual(query["top_p"], ["0.9"])
        self.assertEqual(query["temperature"], ["0.85"])
        self.assertEqual(query["fragment_interval"], ["0.42"])
        self.assertEqual(query["repetition_penalty"], ["1.3"])

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
