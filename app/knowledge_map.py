from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, is_dataclass
from typing import Iterable


MODULE_DEFINITIONS = (
    ("learning-value", "学习价值", "兴趣与思维"),
    ("learning-preparation", "学习准备", "规划与工具"),
    ("learning-methods", "学习方法", "练习与调试"),
    ("cpp-foundations", "基础语法", "输出、变量与运算"),
    ("conditionals", "条件判断", "if 与 if-else"),
    ("loops", "循环结构", "for、while 与累加"),
    ("practice", "练习与项目", "从习题到真实任务"),
    ("course-faq", "课程常见问题", "学习安排与说明"),
    ("learner-cases", "学员案例", "经历与学习动力"),
)


def _record(item: object) -> dict:
    if isinstance(item, dict):
        return dict(item)
    if is_dataclass(item):
        return asdict(item)
    return {
        key: getattr(item, key)
        for key in ("id", "filename", "section", "text", "position")
        if hasattr(item, key)
    }


def _module_for(filename: str, section: str, text: str) -> str:
    filename_text = filename.lower()
    compact = re.sub(r"\s+", "", f"{section} {text}".lower())
    if "学员心得" in filename_text or "学员案例" in filename_text:
        return "learner-cases"
    if "课程问答" in filename_text or "课程qa" in filename_text:
        return "course-faq"
    if section.strip() == "文档开头":
        return "learning-value"
    if re.match(r"2\.\d+", section.strip()):
        return "learning-preparation"
    if re.match(r"3\.\d+", section.strip()):
        return "learning-methods"
    if "学习价值" in compact or any(word in compact for word in ("为什么要学编程", "c++能做什么", "学编程有什么用")):
        return "learning-value"
    if any(word in compact for word in ("学习规划", "电脑配置", "安装什么软件", "自学资源", "适合学习", "什么时候学")):
        return "learning-preparation"
    if any(word in compact for word in ("学习方法", "盲打", "调试", "bug", "四步编程", "正向编程", "反向编程", "保护眼睛", "ai工具")):
        return "learning-methods"
    if "习题" in compact or any(word in compact for word in ("真实项目", "实战训练", "完整闭环")):
        return "practice"
    if re.search(r"第(?:7|8)课", compact) or any(word in compact for word in ("ifelse", "if语句", "条件判断", "奇偶", "比大小", "三角形判定", "成绩评定")):
        return "conditionals"
    if re.search(r"第(?:9|10)课", compact) or any(word in compact for word in ("for循环", "while循环", "循环结构", "高斯求和", "交错求和", "累加")):
        return "loops"
    if re.search(r"第[1-6]课", compact) or any(word in compact for word in ("cout", "cin", "变量", "运算符", "int", "double", "vector", "函数", "数组", "字符串")):
        return "cpp-foundations"
    return "to-organize"


def build_knowledge_map(chunks: Iterable[object], approved: Iterable[dict] = ()) -> dict:
    grouped: dict[str, dict[str, dict]] = {module_id: {} for module_id, _, _ in MODULE_DEFINITIONS}
    grouped["to-organize"] = {}
    total_points = 0

    def add(
        module_id: str, title: str, question: str, source_kind: str, source: str,
        section: str | None = None,
    ) -> None:
        nonlocal total_points
        total_points += 1
        module = grouped[module_id]
        section = section or title
        key = f"{source_kind}:{section}"
        if key not in module:
            digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
            module[key] = {
                "id": f"{module_id}-{digest}", "title": title, "section": section,
                "question": question, "source_kind": source_kind,
                "chunk_count": 0, "sources": [],
            }
        item = module[key]
        item["chunk_count"] += 1
        if source and source not in item["sources"]:
            item["sources"].append(source)

    for raw_chunk in chunks:
        item = _record(raw_chunk)
        filename = str(item.get("filename", "教材"))
        section = str(item.get("section", "未分章节"))
        text = str(item.get("text", ""))
        module_id = _module_for(filename, section, text)
        is_front_matter = section == "文档开头"
        question = f"请给我讲解{section}。" if not is_front_matter else f"请介绍{filename}的主要内容。"
        add(module_id, "教材概览" if is_front_matter else section, question, "document", filename, section)

    for approved_item in approved:
        if approved_item.get("status") != "approved":
            continue
        question = str(approved_item.get("question", "教师补充知识")).strip()
        answer = str(approved_item.get("answer", ""))
        module_id = _module_for("教师审核知识库", question, answer)
        add(module_id, question, question, "reviewed_learning", "教师审核知识库")

    modules = []
    for index, (module_id, title, subtitle) in enumerate(MODULE_DEFINITIONS, start=1):
        items = list(grouped[module_id].values())
        modules.append({
            "id": module_id, "index": index, "title": title, "subtitle": subtitle,
            "count": sum(item["chunk_count"] for item in items), "items": items,
        })
    if grouped["to-organize"]:
        items = list(grouped["to-organize"].values())
        modules.append({
            "id": "to-organize", "index": len(modules) + 1, "title": "待整理",
            "subtitle": "新内容暂存区", "count": sum(item["chunk_count"] for item in items), "items": items,
        })
    return {"total_points": total_points, "modules": modules}
