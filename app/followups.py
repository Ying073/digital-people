from __future__ import annotations

import re


SECTION_PREFIX_RE = re.compile(
    r"^(?:第[\d一二三四五六七八九十百]+课\s*|"
    r"[\d一二三四五六七八九十百]+、\s*|\d+(?:\.\d+)+\s*)"
)


def _topic_from_sources(sources: list[dict]) -> str:
    if not sources:
        return "这个知识点"
    topic = str(sources[0].get("section", "")).strip()
    topic = SECTION_PREFIX_RE.sub("", topic).strip("？? 。！!")
    if not topic or topic == "文档开头":
        return "这个知识点"
    return topic[:18]


def suggest_follow_up_questions(question: str, answer: str, sources: list[dict]) -> list[str]:
    """Return three compact, deterministic next questions without another model call."""
    topic = _topic_from_sources(sources)
    context = re.sub(r"\s+", "", f"{question} {answer} {topic}".lower())

    if any(word in context for word in ("学习规划", "零基础", "怎么学", "自学", "学习周期")):
        return [
            "零基础第一周具体应该做什么？",
            "每天练习多久比较合适？",
            "怎样判断自己真的掌握了？",
        ]
    if any(word in context for word in ("循环", "for", "while", "累加", "求和", "倒计时", "乘法口诀")):
        return [
            "for 循环和 while 循环有什么区别？",
            "循环什么时候会变成死循环？",
            "能出一道循环累加练习吗？",
        ]
    if any(word in context for word in ("条件判断", "if", "else", "奇偶", "比大小", "整除")):
        return [
            "if 和 if-else 有什么区别？",
            "同时判断多个条件应该怎么写？",
            "能出一道条件判断练习吗？",
        ]
    if any(word in context for word in ("变量", "int", "double", "vector", "数组", "字符串")):
        return [
            "变量名应该怎样取才清楚？",
            "int 和 double 有什么区别？",
            "能出一道变量使用练习吗？",
        ]
    if any(word in context for word in ("cout", "cin", "输出", "输入")):
        return [
            "cout 中的 << 是什么意思？",
            "怎样连续输出文字和变量？",
            "能出一道输入输出练习吗？",
        ]
    if any(word in context for word in ("为什么学", "学习价值", "能做什么", "有什么用")):
        return [
            "编程在生活中还有哪些例子？",
            "我现在应该先学哪个知识点？",
            "能给我一个适合入门的小任务吗？",
        ]

    return [
        f"{topic}最容易写错的地方是什么？",
        f"能用更简单的例子解释{topic}吗？",
        f"能出一道关于{topic}的小练习吗？",
    ]
