from __future__ import annotations

import hashlib
import json
import math
import re
import threading
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from docx import Document
from pypdf import PdfReader


SUPPORTED_SUFFIXES = {".docx", ".pdf", ".txt", ".md"}
HEADING_RE = re.compile(
    r"^(?:第[一二三四五六七八九十百0-9]+课|[一二三四五六七八九十百]+、|\d+\.\d+|习题\d+)"
)
LATIN_RE = re.compile(r"[a-zA-Z0-9_+#.%=-]+")
HAN_RE = re.compile(r"[\u3400-\u9fff]+")


@dataclass(slots=True)
class Chunk:
    id: str
    document_id: str
    filename: str
    section: str
    text: str
    position: int


def document_id(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()[:16]


def tokenize(text: str) -> list[str]:
    normalized = text.lower().replace("c＋＋", "c++")
    tokens = LATIN_RE.findall(normalized)
    for run in HAN_RE.findall(normalized):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
            if len(run) <= 6:
                tokens.append(run)
    return tokens


def extract_paragraphs(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        doc = Document(path)
        return [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        paragraphs: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            paragraphs.extend(line.strip() for line in text.splitlines() if line.strip())
        return paragraphs
    return [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def chunk_document(path: Path, max_chars: int = 780) -> list[Chunk]:
    paragraphs = extract_paragraphs(path)
    doc_id = document_id(path)
    chunks: list[Chunk] = []
    section = "文档开头"
    buffer: list[str] = []
    length = 0

    def flush() -> None:
        nonlocal buffer, length
        if not buffer:
            return
        text = "\n".join(buffer)
        position = len(chunks) + 1
        chunks.append(
            Chunk(
                id=f"{doc_id}-{position}",
                document_id=doc_id,
                filename=path.name,
                section=section,
                text=text,
                position=position,
            )
        )
        buffer = []
        length = 0

    for paragraph in paragraphs:
        if HEADING_RE.match(paragraph) or len(paragraph) <= 36 and paragraph.endswith("篇"):
            flush()
            section = paragraph
        if length and length + len(paragraph) + 1 > max_chars:
            flush()
        buffer.append(paragraph)
        length += len(paragraph) + 1
    flush()
    return chunks


class KnowledgeBase:
    def __init__(self, upload_dir: Path, index_path: Path) -> None:
        self.upload_dir = upload_dir
        self.index_path = index_path
        self._lock = threading.RLock()
        self.chunks: list[Chunk] = []
        self.term_counts: list[Counter[str]] = []
        self.doc_frequency: Counter[str] = Counter()
        self.avg_length = 1.0
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.load_or_build()

    def load_or_build(self) -> None:
        with self._lock:
            if self.index_path.exists():
                try:
                    payload = json.loads(self.index_path.read_text(encoding="utf-8"))
                    self.chunks = [Chunk(**item) for item in payload.get("chunks", [])]
                    self._prepare_index()
                    return
                except (OSError, ValueError, TypeError):
                    pass
            self.rebuild()

    def rebuild(self) -> dict[str, int]:
        with self._lock:
            chunks: list[Chunk] = []
            for path in sorted(self.upload_dir.iterdir()):
                if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
                    chunks.extend(chunk_document(path))
            self.chunks = chunks
            self._prepare_index()
            payload = {"version": 1, "chunks": [asdict(chunk) for chunk in chunks]}
            temporary = self.index_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            temporary.replace(self.index_path)
            return {"documents": len(self.list_documents()), "chunks": len(chunks)}

    def _prepare_index(self) -> None:
        self.term_counts = []
        self.doc_frequency = Counter()
        lengths: list[int] = []
        for chunk in self.chunks:
            counts = Counter(tokenize(f"{chunk.section} {chunk.text}"))
            self.term_counts.append(counts)
            lengths.append(sum(counts.values()))
            self.doc_frequency.update(counts.keys())
        self.avg_length = sum(lengths) / len(lengths) if lengths else 1.0

    def search(self, query: str, limit: int = 5) -> list[dict]:
        query_terms = tokenize(query)
        if not query_terms or not self.chunks:
            return []
        query_counts = Counter(query_terms)
        total = len(self.chunks)
        scored: list[tuple[float, int]] = []
        k1, b = 1.5, 0.72
        for index, counts in enumerate(self.term_counts):
            doc_len = max(sum(counts.values()), 1)
            score = 0.0
            for term, query_weight in query_counts.items():
                tf = counts.get(term, 0)
                if not tf:
                    continue
                df = self.doc_frequency[term]
                idf = math.log(1 + (total - df + 0.5) / (df + 0.5))
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * doc_len / self.avg_length)
                score += idf * numerator / denominator * min(query_weight, 2)
            if "学习目标：" in self.chunks[index].text:
                score *= 1.18
            if self.chunks[index].text.lstrip().startswith(('"#include', '"int main')):
                score *= 0.72
            if score > 0:
                scored.append((score, index))
        scored.sort(reverse=True)
        results = []
        for score, index in scored[:limit]:
            chunk = self.chunks[index]
            item = asdict(chunk)
            item["score"] = round(score, 4)
            results.append(item)
        return results

    def list_documents(self) -> list[dict]:
        documents = []
        for path in sorted(self.upload_dir.iterdir()):
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
                documents.append(
                    {
                        "id": document_id(path),
                        "filename": path.name,
                        "size": path.stat().st_size,
                        "modified": path.stat().st_mtime,
                    }
                )
        return documents

    def resolve_document(self, doc_id: str) -> Path | None:
        for path in self.upload_dir.iterdir():
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
                if document_id(path) == doc_id:
                    return path
        return None
