import unittest

from app.style import speech_text


class SpeechTextTests(unittest.TestCase):
    def test_replaces_fenced_code_with_blackboard_cue(self) -> None:
        answer = "先声明变量。\n\n```cpp\nint score = 90;\nscore = 95;\n```\n\n再修改它。"

        self.assertEqual(speech_text(answer), "先声明变量。 代码示例请看黑板。 再修改它。")

    def test_removes_inline_markdown_but_keeps_content(self) -> None:
        answer = "**注意**：`==` 才是比较。请看[教材](https://example.com)。"

        self.assertEqual(speech_text(answer), "注意：== 才是比较。请看教材。")


if __name__ == "__main__":
    unittest.main()
