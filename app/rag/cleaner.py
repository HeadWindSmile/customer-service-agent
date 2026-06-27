import re


class TextCleaner:
    """清洗知识库文本，让分块和检索面对更稳定的中文客服文档内容。"""

    _spaces_pattern = re.compile(r"[ \t\u3000]+")
    _blank_lines_pattern = re.compile(r"\n{3,}")

    def clean(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = []
        for line in normalized.split("\n"):
            line = self._spaces_pattern.sub(" ", line).strip()
            if line:
                lines.append(line)
            elif lines and lines[-1] != "":
                lines.append("")
        cleaned = "\n".join(lines)
        return self._blank_lines_pattern.sub("\n\n", cleaned).strip()

