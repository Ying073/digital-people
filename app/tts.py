from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


VOICE_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
VOICE_STYLES = {"explain", "encourage", "correct", "question", "celebrate", "neutral"}


class TTSServiceError(RuntimeError):
    pass


class VoiceLibrary:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.manifest_path = directory / "manifest.json"
        self.directory.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict]:
        if not self.manifest_path.exists():
            return []
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, list) else []
        except (OSError, ValueError, TypeError):
            return []

    def _write(self, samples: list[dict]) -> None:
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.manifest_path)

    def list(self) -> list[dict]:
        return [
            {
                key: item.get(key, "")
                for key in (
                    "id", "filename", "transcript", "style", "created_at",
                    "source_url", "source_title", "clip_start_seconds", "clip_end_seconds",
                )
            }
            for item in self._read()
        ]

    def get(self, sample_id: str) -> dict | None:
        return next((item for item in self._read() if item.get("id") == sample_id), None)

    def add(self, original_name: str, content: bytes, transcript: str, style: str) -> dict:
        suffix = Path(original_name).suffix.lower()
        if suffix not in VOICE_EXTENSIONS:
            raise TTSServiceError("仅支持 WAV、MP3、FLAC、M4A 和 OGG 音频")
        sample_id = uuid.uuid4().hex
        filename = f"{sample_id}{suffix}"
        (self.directory / filename).write_bytes(content)
        sample = {
            "id": sample_id,
            "filename": filename,
            "transcript": transcript.strip()[:1000],
            "style": style if style in VOICE_STYLES else "neutral",
            "created_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        }
        samples = self._read()
        samples.append(sample)
        self._write(samples)
        return {key: sample[key] for key in ("id", "filename", "transcript", "style", "created_at")}

    def delete(self, sample_id: str) -> bool:
        samples = self._read()
        sample = next((item for item in samples if item.get("id") == sample_id), None)
        if not sample:
            return False
        (self.directory / str(sample.get("filename", ""))).unlink(missing_ok=True)
        self._write([item for item in samples if item.get("id") != sample_id])
        return True


def strip_for_speech(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", "代码示例请看黑板。", text)
    text = re.sub(r"[`*_>#]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1800]


def synthesize_gpt_sovits(
    *,
    text: str,
    service_url: str,
    sample_path: Path,
    prompt_text: str,
    speed: float = 1.0,
    timeout: float = 45.0,
) -> bytes:
    query = urllib.parse.urlencode(
        {
            "text": strip_for_speech(text),
            "text_lang": "zh",
            "ref_audio_path": str(sample_path),
            "prompt_lang": "zh",
            "prompt_text": prompt_text,
            "text_split_method": "cut5",
            "media_type": "wav",
            "streaming_mode": "false",
            "speed_factor": max(0.7, min(float(speed), 1.35)),
        }
    )
    endpoint = service_url.rstrip("/")
    if not endpoint.endswith("/tts"):
        endpoint += "/tts"
    try:
        with urllib.request.urlopen(f"{endpoint}?{query}", timeout=timeout) as response:
            payload = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as error:
        raise TTSServiceError(f"GPT-SoVITS 服务不可用: {error}") from error
    if not payload or len(payload) < 44:
        raise TTSServiceError("GPT-SoVITS 返回了空音频")
    return payload


def synthesize_windows_sapi(text: str, speed: float = 1.0) -> bytes:
    """Render a local Chinese Windows voice without sending the answer to another service."""
    script = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $voice = $speaker.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -eq 'zh-CN' } | Select-Object -First 1
    if (-not $voice) { throw '没有安装中文系统语音' }
    $speaker.SelectVoice($voice.VoiceInfo.Name)
    $speaker.Rate = [int]$env:XIXI_SPEECH_RATE
    $speaker.SetOutputToWaveFile($env:XIXI_SPEECH_FILE)
    $speaker.Speak($env:XIXI_SPEECH_TEXT)
} finally {
    $speaker.Dispose()
}
"""
    with tempfile.TemporaryDirectory(prefix="xixi-speech-") as directory:
        output = Path(directory) / "answer.wav"
        environment = os.environ.copy()
        environment.update({
            "XIXI_SPEECH_TEXT": strip_for_speech(text),
            "XIXI_SPEECH_FILE": str(output),
            "XIXI_SPEECH_RATE": str(round((max(0.7, min(speed, 1.35)) - 1) * 10)),
        })
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                env=environment, capture_output=True, timeout=120, check=False,
            )
            if result.returncode != 0 or not output.is_file():
                raise TTSServiceError("本机中文语音不可用")
            audio = output.read_bytes()
        except (OSError, subprocess.TimeoutExpired) as error:
            raise TTSServiceError("本机中文语音合成失败") from error
    if len(audio) < 44 or not audio.startswith(b"RIFF"):
        raise TTSServiceError("本机语音返回了无效音频")
    return audio
