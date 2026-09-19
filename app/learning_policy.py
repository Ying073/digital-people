from __future__ import annotations

import re

from .learning import redact_sensitive_text


AUTO_PUBLISH_CONFIDENCE = 0.92

_UNCERTAIN_MARKERS = (
    "可能", "也许", "大概", "不确定", "据说", "听说", "目前", "最新", "暂时",
    "仅供参考", "以实际为准", "以官方为准",
)
_MANUAL_REVIEW_MARKERS = (
    "收费", "价格", "学费", "退款", "退费", "报名", "优惠", "名额",
    "升学", "就业", "工资", "薪资", "实习", "证书", "推荐信",
    "课程承诺", "政策", "医疗", "法律", "政治",
    "账号", "密码", "api key", "联系方式", "手机号", "邮箱",
)
_URL_RE = re.compile(r"(?:https?://|www\.)", re.IGNORECASE)


def auto_publish_allowed(question: str, review: dict) -> bool:
    """Apply deterministic safety gates after the model's semantic review."""
    if review.get("decision") != "auto_publish":
        return False
    confidence = review.get("confidence")
    if isinstance(confidence, bool):
        return False
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        return False
    if confidence_value < AUTO_PUBLISH_CONFIDENCE or confidence_value > 1:
        return False

    canonical_question = str(review.get("canonical_question", "")).strip()
    canonical_answer = str(review.get("canonical_answer", "")).strip()
    if not canonical_question or not canonical_answer:
        return False
    if len(canonical_question) > 200 or len(canonical_answer) > 2000:
        return False

    content = " ".join((question.strip(), canonical_question, canonical_answer))
    if redact_sensitive_text(content) != content:
        return False
    lowered = content.lower()
    if _URL_RE.search(lowered):
        return False
    if any(marker in lowered for marker in _UNCERTAIN_MARKERS):
        return False
    if any(marker in lowered for marker in _MANUAL_REVIEW_MARKERS):
        return False
    return True
