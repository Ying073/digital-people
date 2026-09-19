from __future__ import annotations

import json
import re
import threading
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .knowledge import tokenize


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
LONG_NUMBER_RE = re.compile(r"(?<!\d)\d{12,18}(?!\d)")
TRIVIAL_MESSAGES = {"你好", "您好", "嗨", "hello", "hi", "谢谢", "谢谢老师", "好的", "再见"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_question(question: str) -> str:
    normalized = question.lower().replace("c＋＋", "c++")
    return re.sub(r"[^a-z0-9+#\u3400-\u9fff]+", "", normalized)


def redact_sensitive_text(text: str) -> str:
    text = EMAIL_RE.sub("[邮箱]", text)
    text = PHONE_RE.sub("[手机号]", text)
    return LONG_NUMBER_RE.sub("[长数字]", text)


def is_learning_candidate(question: str) -> bool:
    compact = re.sub(r"\s+", "", question).strip("，。！？!?~～")
    if compact.lower() in TRIVIAL_MESSAGES:
        return False
    return len(normalize_question(compact)) >= 4


class LearningStore:
    """JSON-backed review queue and teacher-approved supplemental knowledge."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict:
        if not self.path.exists():
            return {"version": 1, "items": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            items = payload.get("items", []) if isinstance(payload, dict) else []
            return {"version": 1, "items": items if isinstance(items, list) else []}
        except (OSError, ValueError, TypeError):
            return {"version": 1, "items": []}

    def _write(self, payload: dict) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def record_gap(self, question: str, draft_answer: str, top_score: float | None) -> dict:
        question = redact_sensitive_text(question.strip())[:1000]
        draft_answer = redact_sensitive_text(draft_answer.strip())[:12000]
        key = normalize_question(question)
        if not key:
            raise ValueError("问题不能为空")
        with self._lock:
            payload = self._read()
            timestamp = _now()
            for item in payload["items"]:
                if item.get("status") == "pending" and item.get("normalized_question") == key:
                    item["question"] = question
                    item["draft_answer"] = draft_answer
                    item["occurrences"] = int(item.get("occurrences", 1)) + 1
                    item["last_seen_at"] = timestamp
                    item["top_score"] = top_score
                    self._write(payload)
                    return dict(item)
            item = {
                "id": uuid.uuid4().hex,
                "question": question,
                "normalized_question": key,
                "draft_answer": draft_answer,
                "answer": "",
                "status": "pending",
                "occurrences": 1,
                "top_score": top_score,
                "first_seen_at": timestamp,
                "last_seen_at": timestamp,
                "reviewed_at": None,
            }
            payload["items"].append(item)
            self._write(payload)
            return dict(item)

    def list_candidates(self) -> list[dict]:
        with self._lock:
            items = [dict(item) for item in self._read()["items"] if item.get("status") == "pending"]
        return sorted(items, key=lambda item: (int(item.get("occurrences", 1)), item.get("last_seen_at", "")), reverse=True)

    def list_approved(self) -> list[dict]:
        with self._lock:
            return [dict(item) for item in self._read()["items"] if item.get("status") == "approved"]

    def approve(self, candidate_id: str, answer: str) -> dict:
        answer = redact_sensitive_text(answer.strip())
        if not answer:
            raise ValueError("审核答案不能为空")
        with self._lock:
            payload = self._read()
            for item in payload["items"]:
                if item.get("id") == candidate_id and item.get("status") == "pending":
                    item["answer"] = answer[:12000]
                    item["status"] = "approved"
                    item["reviewed_at"] = _now()
                    self._write(payload)
                    return dict(item)
        raise KeyError(candidate_id)

    def reject(self, candidate_id: str) -> dict:
        with self._lock:
            payload = self._read()
            for item in payload["items"]:
                if item.get("id") == candidate_id and item.get("status") == "pending":
                    item["status"] = "rejected"
                    item["reviewed_at"] = _now()
                    self._write(payload)
                    return dict(item)
        raise KeyError(candidate_id)

    def search_approved(self, query: str, limit: int = 5) -> list[dict]:
        query_counts = Counter(tokenize(query))
        if not query_counts:
            return []
        with self._lock:
            approved = [dict(item) for item in self._read()["items"] if item.get("status") == "approved"]
        scored: list[tuple[float, dict]] = []
        for item in approved:
            counts = Counter(tokenize(f"{item.get('question', '')} {item.get('answer', '')}"))
            overlap = sum(min(weight, counts.get(term, 0)) for term, weight in query_counts.items())
            if not overlap:
                continue
            coverage = overlap / max(sum(query_counts.values()), 1)
            score = 10.0 + coverage
            result = {
                "id": f"learned-{item['id']}",
                "document_id": "reviewed-learning",
                "filename": "教师审核知识库",
                "section": item.get("question", "补充知识"),
                "text": item.get("answer", ""),
                "position": 1,
                "score": round(score, 4),
                "source_kind": "reviewed_learning",
            }
            scored.append((score, result))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:limit]]
