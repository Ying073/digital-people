from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .knowledge import KnowledgeBase, SUPPORTED_SUFFIXES
from .knowledge_map import build_knowledge_map
from .followups import suggest_follow_up_questions
from .learning import LearningStore, is_learning_candidate
from .llm import LLMError, chat_completion, extractive_answer
from .style import avatar_state_for, classify_emotion, local_paraphrase, needs_rewrite, speech_text
from .tts import TTSServiceError, VOICE_EXTENSIONS, VoiceLibrary, gpt_sovits_status, synthesize_gpt_sovits, synthesize_windows_sapi


ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
SETTINGS_PATH = DATA / "settings.json"
INDEX_PATH = DATA / "knowledge_index.json"
VOICE_SAMPLES = DATA / "voice_samples"
TTS_CACHE = DATA / "tts_cache"
LEARNING_PATH = DATA / "learning_store.json"
DATA.mkdir(exist_ok=True)
TTS_CACHE.mkdir(exist_ok=True)

app = FastAPI(title="西西编程伙伴", version="0.1.0")
knowledge = KnowledgeBase(UPLOADS, INDEX_PATH)
learning_store = LearningStore(LEARNING_PATH)
voice_library = VoiceLibrary(VOICE_SAMPLES)
logger = logging.getLogger("xixi")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[dict] = Field(default_factory=list)


class SettingsRequest(BaseModel):
    base_url: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=200)
    api_key: str = Field(default="", max_length=1000)


class VoiceSettingsRequest(BaseModel):
    service_url: str = Field(default="http://127.0.0.1:9880", max_length=500)
    default_sample_id: str = Field(default="", max_length=80)
    style_sample_ids: dict[str, str] = Field(default_factory=dict)
    allow_browser_fallback: bool = True
    speed: float = Field(default=0.94, ge=0.7, le=1.35)
    volume: float = Field(default=1.0, ge=0.2, le=1.0)


class VoiceTestRequest(BaseModel):
    text: str = Field(default="你好，我是西西老师。我们一起把编程问题变简单。", min_length=1, max_length=800)
    sample_id: str = Field(default="", max_length=80)


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)


class LearningApprovalRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)


def read_settings() -> dict[str, str]:
    defaults = {
        "base_url": os.getenv("OPENAI_BASE_URL", ""),
        "model": os.getenv("OPENAI_MODEL", ""),
        "api_key": os.getenv("OPENAI_API_KEY", ""),
    }
    if SETTINGS_PATH.exists():
        try:
            saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            defaults.update({key: str(saved.get(key, defaults[key])) for key in defaults})
        except (OSError, ValueError, TypeError):
            pass
    return defaults


def read_voice_settings() -> dict:
    defaults = {
        "service_url": os.getenv("GPT_SOVITS_URL", "http://127.0.0.1:9880"),
        "default_sample_id": os.getenv("GPT_SOVITS_SAMPLE_ID", ""),
        "style_sample_ids": {},
        "allow_browser_fallback": True,
        "speed": 0.94,
        "volume": 1.0,
    }
    if SETTINGS_PATH.exists():
        try:
            payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            saved = payload.get("voice", {}) if isinstance(payload, dict) else {}
            if isinstance(saved, dict):
                defaults.update({key: saved[key] for key in defaults if key in saved})
        except (OSError, ValueError, TypeError):
            pass
    return defaults


def write_settings(payload: dict) -> None:
    temporary = SETTINGS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(SETTINGS_PATH)


def audio_response_for(answer: str, emotion: str) -> tuple[str | None, str]:
    voice = read_voice_settings()
    fallback = "system" if sys.platform == "win32" else "browser"
    fallback = fallback if voice.get("allow_browser_fallback", True) else "none"
    style_ids = voice.get("style_sample_ids", {})
    sample_id = ""
    if isinstance(style_ids, dict):
        sample_id = str(style_ids.get(emotion, ""))
    sample_id = sample_id or str(voice.get("default_sample_id", ""))
    sample = voice_library.get(sample_id) if sample_id else None
    if not sample:
        return (None, fallback)
    path = VOICE_SAMPLES / str(sample.get("filename", ""))
    if not path.is_file():
        return (None, fallback)
    try:
        audio = synthesize_gpt_sovits(
            text=answer,
            service_url=str(voice.get("service_url", "http://127.0.0.1:9880")),
            sample_path=path,
            prompt_text=str(sample.get("transcript", "")),
            speed=float(voice.get("speed", 0.94)),
        )
        audio_id = uuid.uuid4().hex
        (TTS_CACHE / f"{audio_id}.wav").write_bytes(audio)
        return (audio_id, "gpt_sovits")
    except TTSServiceError as error:
        logger.warning("TTS failed: %s", error)
        return (None, fallback)


def require_admin(password: str | None) -> None:
    expected = os.getenv("ADMIN_PASSWORD", "teacher123")
    if not password or password != expected:
        raise HTTPException(status_code=401, detail="教师密码不正确")


def public_sources(results: list[dict]) -> list[dict]:
    return [
        {
            "filename": item["filename"],
            "section": item["section"],
            "excerpt": item["text"][:220],
            "score": item["score"],
            "kind": item.get("source_kind", "document"),
        }
        for item in results
    ]


@app.get("/api/status")
def status() -> dict:
    settings = read_settings()
    voice = read_voice_settings()
    voice_sample = voice_library.get(str(voice.get("default_sample_id", "")))
    return {
        "model_configured": bool(settings["base_url"] and settings["model"] and settings["api_key"]),
        "voice_configured": bool(voice_sample and voice_sample.get("filename")),
        "documents": len(knowledge.list_documents()),
        "chunks": len(knowledge.chunks),
    }


@app.get("/api/knowledge-map")
def knowledge_map() -> dict:
    return build_knowledge_map(knowledge.chunks, learning_store.list_approved())


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict:
    message = request.message.strip()
    document_results = knowledge.search(message, limit=5)
    reviewed_results = learning_store.search_approved(message, limit=5)
    results = sorted(document_results + reviewed_results, key=lambda item: item["score"], reverse=True)[:5]
    settings = read_settings()
    configured = bool(settings["base_url"] and settings["model"] and settings["api_key"])
    style_examples = [item.get("transcript", "") for item in voice_library.list()]
    if configured:
        context_parts = []
        for index, item in enumerate(results, start=1):
            context_parts.append(
                f"[来源{index}] 文件：{item['filename']}；章节：{item['section']}\n{item['text']}"
            )
        context = "\n\n".join(context_parts) if context_parts else "未检索到相关教材片段。"
        try:
            answer = chat_completion(
                base_url=settings["base_url"],
                api_key=settings["api_key"],
                model=settings["model"],
                message=message,
                context=context,
                history=request.history,
                teacher_style_examples=style_examples,
            )
            if not answer.strip():
                raise LLMError("模型返回空答案")
            mode = "model"
            if needs_rewrite(answer, [item["text"] for item in results]):
                answer = chat_completion(
                    base_url=settings["base_url"],
                    api_key=settings["api_key"],
                    model=settings["model"],
                    message=message,
                    context=context,
                    history=request.history,
                    force_rewrite=True,
                    teacher_style_examples=style_examples,
                )
                if not answer.strip():
                    raise LLMError("模型重写后返回空答案")
                if needs_rewrite(answer, [item["text"] for item in results]):
                    answer = local_paraphrase(message, results)
                    mode = "local_rephrase"
        except LLMError as error:
            answer = extractive_answer(message, results)
            answer += "\n\n模型暂时没有接通，已切换到本地规则改述模式。"
            mode = "fallback"
            logger.warning("LLM failed: %s", error)
    else:
        answer = extractive_answer(message, results)
        mode = "local_rephrase"
    emotion = classify_emotion(message, answer)
    spoken_answer = speech_text(answer)
    audio_id, tts_mode = audio_response_for(spoken_answer, emotion)
    voice = read_voice_settings()
    top_score = float(results[0]["score"]) if results else None
    knowledge_gap_recorded = (not results or top_score < 1.0) and is_learning_candidate(message)
    if knowledge_gap_recorded:
        try:
            learning_store.record_gap(message, answer, top_score)
        except (OSError, ValueError) as error:
            knowledge_gap_recorded = False
            logger.warning("Could not record knowledge gap: %s", error)
    return {
        "answer": answer,
        "speech_text": spoken_answer,
        "sources": public_sources(results[:3]),
        "mode": mode,
        "emotion": emotion,
        "avatar_state": avatar_state_for(emotion),
        "audio_url": f"/api/audio/{audio_id}" if audio_id else None,
        "tts_mode": tts_mode,
        "browser_fallback": bool(voice.get("allow_browser_fallback", True)),
        "volume": float(voice.get("volume", 1.0)),
        "knowledge_gap_recorded": knowledge_gap_recorded,
        "follow_up_questions": suggest_follow_up_questions(message, answer, results),
    }


@app.post("/api/admin/login")
def admin_login(x_admin_password: str | None = Header(default=None)) -> dict:
    require_admin(x_admin_password)
    return {"ok": True}


@app.get("/api/admin/documents")
def admin_documents(x_admin_password: str | None = Header(default=None)) -> dict:
    require_admin(x_admin_password)
    return {"documents": knowledge.list_documents(), "chunks": len(knowledge.chunks)}


@app.get("/api/admin/learning-candidates")
def admin_learning_candidates(x_admin_password: str | None = Header(default=None)) -> dict:
    require_admin(x_admin_password)
    candidates = learning_store.list_candidates()
    return {"candidates": candidates, "pending": len(candidates)}


@app.post("/api/admin/learning-candidates/{candidate_id}/approve")
def approve_learning_candidate(
    candidate_id: str,
    request: LearningApprovalRequest,
    x_admin_password: str | None = Header(default=None),
) -> dict:
    require_admin(x_admin_password)
    try:
        item = learning_store.approve(candidate_id, request.answer)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="待审核问题不存在") from error
    return {"ok": True, "item": item}


@app.post("/api/admin/learning-candidates/{candidate_id}/reject")
def reject_learning_candidate(
    candidate_id: str,
    x_admin_password: str | None = Header(default=None),
) -> dict:
    require_admin(x_admin_password)
    try:
        item = learning_store.reject(candidate_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="待审核问题不存在") from error
    return {"ok": True, "item": item}


@app.post("/api/admin/documents")
async def upload_document(
    file: UploadFile = File(...),
    x_admin_password: str | None = Header(default=None),
) -> dict:
    require_admin(x_admin_password)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=400, detail="仅支持 DOCX、PDF、TXT 和 Markdown")
    safe_name = re.sub(r"[^\w\-.()\u3400-\u9fff]", "_", Path(file.filename or f"document{suffix}").name)
    target = UPLOADS / safe_name
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    try:
        stats = knowledge.rebuild()
    except Exception as error:
        target.unlink(missing_ok=True)
        knowledge.rebuild()
        raise HTTPException(status_code=400, detail=f"无法读取该文件: {error}") from error
    return {"ok": True, **stats}


@app.delete("/api/admin/documents/{doc_id}")
def delete_document(doc_id: str, x_admin_password: str | None = Header(default=None)) -> dict:
    require_admin(x_admin_password)
    target = knowledge.resolve_document(doc_id)
    if target is None:
        raise HTTPException(status_code=404, detail="资料不存在")
    target.unlink()
    stats = knowledge.rebuild()
    return {"ok": True, **stats}


@app.post("/api/admin/reindex")
def reindex(x_admin_password: str | None = Header(default=None)) -> dict:
    require_admin(x_admin_password)
    return {"ok": True, **knowledge.rebuild()}


@app.get("/api/admin/settings")
def get_settings(x_admin_password: str | None = Header(default=None)) -> dict:
    require_admin(x_admin_password)
    settings = read_settings()
    return {
        "base_url": settings["base_url"],
        "model": settings["model"],
        "api_key_set": bool(settings["api_key"]),
    }


@app.put("/api/admin/settings")
def update_settings(
    request: SettingsRequest,
    x_admin_password: str | None = Header(default=None),
) -> dict:
    require_admin(x_admin_password)
    current = read_settings()
    base_url = request.base_url.strip()
    model = request.model.strip()
    api_key = request.api_key.strip() or current["api_key"]
    if base_url and not base_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Base URL 必须以 http:// 或 https:// 开头")
    payload = {}
    if SETTINGS_PATH.exists():
        try:
            loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except (OSError, ValueError, TypeError):
            payload = {}
    payload.update({"base_url": base_url, "model": model, "api_key": api_key})
    write_settings(payload)
    return {"ok": True, "configured": bool(base_url and model and api_key)}


@app.get("/api/audio/{audio_id}")
def audio_file(audio_id: str) -> Response:
    if not re.fullmatch(r"[a-f0-9]{32}", audio_id):
        raise HTTPException(status_code=404, detail="音频不存在")
    path = TTS_CACHE / f"{audio_id}.wav"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="音频不存在")
    return FileResponse(path, media_type="audio/wav", filename=f"{audio_id}.wav")


@app.post("/api/speech")
def speech_audio(request: SpeechRequest) -> dict:
    if sys.platform != "win32" or not read_voice_settings().get("allow_browser_fallback", True):
        raise HTTPException(status_code=503, detail="本机语音未启用")
    try:
        audio = synthesize_windows_sapi(request.text, speed=float(read_voice_settings().get("speed", 0.94)))
    except TTSServiceError as error:
        logger.warning("System speech failed: %s", error)
        raise HTTPException(status_code=503, detail=str(error)) from error
    audio_id = uuid.uuid4().hex
    (TTS_CACHE / f"{audio_id}.wav").write_bytes(audio)
    return {"audio_url": f"/api/audio/{audio_id}"}


@app.get("/api/admin/voice-samples")
def admin_voice_samples(x_admin_password: str | None = Header(default=None)) -> dict:
    require_admin(x_admin_password)
    return {"samples": voice_library.list()}


@app.post("/api/admin/voice-samples")
async def upload_voice_sample(
    file: UploadFile = File(...),
    transcript: str = Form(default=""),
    style: str = Form(default="neutral"),
    consent: bool = Form(default=False),
    x_admin_password: str | None = Header(default=None),
) -> dict:
    require_admin(x_admin_password)
    if not consent:
        raise HTTPException(status_code=400, detail="请确认已获得录音本人授权")
    if not transcript.strip():
        raise HTTPException(status_code=400, detail="请填写参考音频逐字稿")
    content = await file.read()
    if len(content) > 30 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="单个声音样本不能超过 30 MB")
    try:
        sample = voice_library.add(file.filename or "sample.wav", content, transcript, style)
    except TTSServiceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    # The first authorized sample becomes the active digital-human voice automatically.
    settings = read_settings()
    voice = read_voice_settings()
    if not voice.get("default_sample_id"):
        voice["default_sample_id"] = sample["id"]
    style_ids = voice.get("style_sample_ids", {})
    if isinstance(style_ids, dict) and style in {"encourage", "correct", "celebrate", "explain"}:
        style_ids[style] = sample["id"]
        voice["style_sample_ids"] = style_ids
    settings["voice"] = voice
    write_settings(settings)
    return {"ok": True, "sample": sample}


@app.delete("/api/admin/voice-samples/{sample_id}")
def delete_voice_sample(sample_id: str, x_admin_password: str | None = Header(default=None)) -> dict:
    require_admin(x_admin_password)
    if not voice_library.delete(sample_id):
        raise HTTPException(status_code=404, detail="声音样本不存在")
    voice = read_voice_settings()
    if voice.get("default_sample_id") == sample_id:
        voice["default_sample_id"] = ""
        settings = read_settings()
        settings["voice"] = voice
        write_settings(settings)
    return {"ok": True}


@app.get("/api/admin/voice-settings")
def get_voice_settings(x_admin_password: str | None = Header(default=None)) -> dict:
    require_admin(x_admin_password)
    voice = read_voice_settings()
    return {**voice, "samples": voice_library.list()}


@app.get("/api/admin/voice-service-status")
def voice_service_status(x_admin_password: str | None = Header(default=None)) -> dict:
    require_admin(x_admin_password)
    service_url = str(read_voice_settings().get("service_url", "http://127.0.0.1:9880"))
    return {**gpt_sovits_status(service_url), "service_url": service_url}


@app.put("/api/admin/voice-settings")
def put_voice_settings(
    request: VoiceSettingsRequest,
    x_admin_password: str | None = Header(default=None),
) -> dict:
    require_admin(x_admin_password)
    if request.default_sample_id and not voice_library.get(request.default_sample_id):
        raise HTTPException(status_code=400, detail="默认声音样本不存在")
    for emotion, sample_id in request.style_sample_ids.items():
        if emotion not in {"welcome", "encourage", "explain", "correct", "celebrate"}:
            raise HTTPException(status_code=400, detail=f"不支持的语气标签: {emotion}")
        if sample_id and not voice_library.get(sample_id):
            raise HTTPException(status_code=400, detail=f"语气样本不存在: {emotion}")
    if not request.service_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="语音服务地址必须以 http:// 或 https:// 开头")
    settings = read_settings()
    settings["voice"] = request.model_dump()
    write_settings(settings)
    return {"ok": True}


@app.post("/api/admin/voice-test")
def voice_test(
    request: VoiceTestRequest,
    x_admin_password: str | None = Header(default=None),
) -> dict:
    require_admin(x_admin_password)
    voice = read_voice_settings()
    sample_id = request.sample_id or str(voice.get("default_sample_id", ""))
    sample = voice_library.get(sample_id)
    if not sample:
        raise HTTPException(status_code=400, detail="请先上传并选择声音样本")
    path = VOICE_SAMPLES / str(sample.get("filename", ""))
    try:
        audio = synthesize_gpt_sovits(
            text=request.text,
            service_url=str(voice.get("service_url", "http://127.0.0.1:9880")),
            sample_path=path,
            prompt_text=str(sample.get("transcript", "")),
            speed=float(voice.get("speed", 0.94)),
        )
    except TTSServiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    audio_id = uuid.uuid4().hex
    (TTS_CACHE / f"{audio_id}.wav").write_bytes(audio)
    return {"audio_url": f"/api/audio/{audio_id}"}


@app.get("/")
def classroom_page() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(STATIC / "admin.html")


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
