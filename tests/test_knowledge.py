import tempfile
import unittest
from pathlib import Path

from app.knowledge import KnowledgeBase, chunk_document, tokenize
from app.style import local_paraphrase, needs_rewrite, paraphrase_overlap


class KnowledgeTests(unittest.TestCase):
    def test_chinese_tokenizer_emits_bigrams(self):
        tokens = tokenize("怎样判断奇偶数？C++")
        self.assertIn("奇偶", tokens)
        self.assertIn("c++", tokens)

    def test_retrieval_prefers_relevant_section(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            uploads = root / "uploads"
            uploads.mkdir()
            (uploads / "lesson.txt").write_text(
                "第1课 欢迎语\ncout可以向屏幕输出文字。\n"
                "第7课 整数奇偶判断\n用整数除以2取余，余数为0就是偶数。",
                encoding="utf-8",
            )
            kb = KnowledgeBase(uploads, root / "index.json")
            results = kb.search("怎么判断奇数偶数")
            self.assertTrue(results)
            self.assertIn("奇偶", results[0]["section"])

    def test_chunk_document_tracks_headings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lesson.md"
            path.write_text("第1课 输出\n学习cout。\n第2课 变量\n学习int。", encoding="utf-8")
            chunks = chunk_document(path)
            self.assertEqual([chunk.section for chunk in chunks], ["第1课 输出", "第2课 变量"])

    def test_local_fallback_rephrases_without_copying_source(self):
        source = [{
            "section": "第7课 整数奇偶判断",
            "text": "在编程中，统一通过对2取余判定整数奇偶：整数对2取余结果为0，说明可以被2整除，为偶数；取余结果不为0，说明无法被2整除，为奇数。",
        }]
        answer = local_paraphrase("怎样判断奇数和偶数？", source)
        self.assertIn("余数", answer)
        self.assertNotIn(source[0]["text"], answer)
        self.assertLess(paraphrase_overlap(answer, [source[0]["text"]]), 0.34)
        self.assertFalse(needs_rewrite(answer, [source[0]["text"]]))


if __name__ == "__main__":
    unittest.main()
