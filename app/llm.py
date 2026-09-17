from __future__ import annotations

import json
import urllib.error
import urllib.request


SYSTEM_PROMPT = """你是“西西编程伙伴”，一位面向小学三年级以上学生的 C++ 启蒙老师。
回答要求：
1. 优先依据提供的教材片段回答，不编造教材中没有的章节或结论。
2. 可以补充稳定的编程常识，但要用“补充说明”明确区分。
3. 语言亲切、准确、短句为主；先给结论，再用步骤或例子解释。
4. 涉及代码时使用标准 C++，所有多行代码必须放在带 cpp 语言标记的 Markdown 围栏代码块中；指出教材示例中可能导致编译错误的地方，但不要嘲讽教材。
5. 不向儿童索取姓名、学校、地址、电话等个人信息。
6. 回答控制在 350 个汉字以内，除非用户明确要求展开。
7. 必须理解教材后重新组织表达，不要逐句复述教材，不要以“教材原文是”开头，也不要连续复制超过 12 个汉字。
8. 用适合小学生的例子解释；代码只保留真正有助于理解的最小片段。
"""


class LLMError(RuntimeError):
    pass


def chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    message: str,
    context: str,
    history: list[dict],
    force_rewrite: bool = False,
    teacher_style_examples: list[str] | None = None,
) -> str:
    endpoint = base_url.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"
    style_examples = [item.strip()[:500] for item in (teacher_style_examples or []) if item.strip()]
    style_prompt = ""
    if style_examples:
        joined = "\n".join(f"- {item}" for item in style_examples[:6])
        style_prompt = (
            "\n以下是已获授权的老师表达样例。只学习句长、停顿、鼓励方式和讲解结构，"
            "不要复制样例内容或个人信息：\n" + joined
        )
    messages = [{"role": "system", "content": SYSTEM_PROMPT + style_prompt}]
    for item in history[-8:]:
        role = item.get("role")
        content = str(item.get("content", ""))[:1200]
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    rewrite_hint = (
        "上一次草稿与资料过于相似，请完全换一种说法，只保留事实和推理，不要复制原句。"
        if force_rewrite
        else "先理解资料，再用自己的话回答，不要照抄资料。"
    )
    user_content = (
        f"教材检索片段：\n{context}\n\n"
        f"学生问题：{message}\n\n"
        f"请依据教材优先回答。若片段不足，可补充常识并明确标注。{rewrite_hint}"
    )
    messages.append({"role": "user", "content": user_content})
    body = json.dumps(
        {"model": model, "messages": messages, "temperature": 0.35, "max_tokens": 700},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise LLMError(f"模型服务返回 {error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise LLMError(f"无法连接模型服务: {error}") from error
    try:
        return payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as error:
        raise LLMError("模型服务返回了无法识别的数据格式") from error


def extractive_answer(message: str, sources: list[dict]) -> str:
    from .style import local_paraphrase

    return local_paraphrase(message, sources)
