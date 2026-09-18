from __future__ import annotations

import re
from collections.abc import Iterable


EMOTIONS = {"welcome", "encourage", "explain", "correct", "celebrate"}


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def speech_text(text: str) -> str:
    """Convert a Markdown answer into natural text for speech synthesis."""
    spoken = re.sub(r"```[^\n`]*\n?[\s\S]*?```", " 代码示例请看黑板。 ", text)
    spoken = re.sub(r"`([^`]+)`", r"\1", spoken)
    spoken = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", spoken)
    spoken = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", spoken)
    spoken = re.sub(r"(?:\*\*|__)(.+?)(?:\*\*|__)", r"\1", spoken)
    spoken = re.sub(r"^[>#\-+]+\s*", "", spoken, flags=re.MULTILINE)
    return _compact(spoken)


def paraphrase_overlap(answer: str, source_texts: Iterable[str]) -> float:
    """Return the largest contiguous character overlap with any source chunk."""
    answer = _compact(answer)
    if len(answer) < 24:
        return 0.0
    answer_grams = {answer[i : i + 8] for i in range(len(answer) - 7)}
    if not answer_grams:
        return 0.0
    largest = 0.0
    for source in source_texts:
        source = _compact(source)
        if len(source) < 8:
            continue
        source_grams = {source[i : i + 8] for i in range(len(source) - 7)}
        largest = max(largest, len(answer_grams & source_grams) / len(answer_grams))
    return round(largest, 4)


def needs_rewrite(answer: str, source_texts: Iterable[str]) -> bool:
    return paraphrase_overlap(answer, source_texts) >= 0.34


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def local_paraphrase(question: str, sources: list[dict]) -> str:
    """Make a short fact-based explanation without copying a chunk verbatim."""
    if not sources:
        return "我暂时没有找到这道题对应的教材知识点。可以换一种问法，或者请老师补充相关资料。"
    if sources[0].get("source_kind") == "reviewed_learning":
        return str(sources[0].get("text", "")).strip()
    query = _compact(question).lower()
    section = sources[0].get("section", "这部分教材")
    combined = _compact(" ".join(str(item.get("text", "")) for item in sources[:3]))
    if _has_any(query, ("奇偶", "奇数", "偶数")) or _has_any(combined, ("奇偶判断", "取余判断奇偶")):
        return "判断奇偶数可以看它除以 2 的余数：余数是 0 就是偶数，否则就是奇数。\n\n```cpp\nif (n % 2 == 0) {\n    cout << \"偶数\";\n} else {\n    cout << \"奇数\";\n}\n```"
    if _has_any(query, ("cout", "输出", "欢迎语")):
        return "cout 是 C++ 的屏幕输出工具。把文字或变量放在 `<<` 后面，就能按顺序显示出来；需要换行时可以接 `endl`。\n\n```cpp\ncout << \"Hello!\" << endl;\n```"
    if _has_any(query, ("for", "循环", "高斯", "求和")):
        return "for 循环适合重复做固定次数的事情。先把累加器设为 0，再让计数器从起点走到终点，每轮把当前数字加进去，最后得到总和。\n\n```cpp\nint sum = 0;\nfor (int i = 1; i <= 10; i++) {\n    sum += i;\n}\ncout << sum;\n```"
    if _has_any(query, ("变量", "int", "整数")):
        return "变量可以理解成一个有名字的盒子，用来保存数据。`int` 适合保存整数，先声明变量，再赋值。\n\n```cpp\nint score = 90;\nscore = 95;\n```"
    if _has_any(query, ("盲打", "学习方法", "规划", "三年级")):
        return "教材建议先把电脑操作和打字练熟，再逐步学习 C++。三年级以上通常已经具备基础数学、专注和自主修改错误的能力，适合从简单程序开始。"
    if _has_any(query, ("if", "条件", "判断", "大小")):
        return "条件判断就是让电脑根据不同情况选择不同动作。先写出要检查的条件，再在 if 或 else 分支中安排对应结果；注意 `=` 是赋值，`==` 才是比较相等。"
    if _has_any(query, ("面积", "周长", "体积", "半径")):
        return "这类题的关键是先把数学公式写清楚，再把已知量放进变量。常量可以保存不会改变的 π 等数据，最后用 cout 输出计算结果。"
    if "学习价值" in section or "为什么" in query:
        return "教材把编程看成一种主动解决问题的练习：写代码、运行、发现错误、再修改。这个过程能同时训练专注力、逻辑思维和把数学知识应用到实际问题的能力。"
    return f"教材在“{section}”中讲的是一个基础编程知识点。建议先抓住它解决的问题，再看变量、条件或循环分别承担什么任务，最后亲手改一个数字验证结果。"


def classify_emotion(question: str, answer: str) -> str:
    text = f"{question} {answer}"
    if _has_any(text, ("错误", "报错", "bug", "注意", "不要把", "区别")):
        return "correct"
    if _has_any(text, ("太棒", "成功", "完成", "恭喜", "正确", "答案是")):
        return "celebrate"
    if _has_any(text, ("为什么", "怎样", "如何", "建议", "可以先")):
        return "encourage"
    return "explain"


def avatar_state_for(emotion: str) -> str:
    return {
        "welcome": "wave",
        "encourage": "encourage",
        "explain": "explain",
        "correct": "correct",
        "celebrate": "celebrate",
    }.get(emotion, "explain")
