from pathlib import Path

from app.rag.cleaner import TextCleaner
from app.rag.document import KnowledgeDocument


class KnowledgeLoader:
    """从知识库目录加载 Markdown/TXT，保持文件读取和检索逻辑解耦。"""

    supported_suffixes = {".md", ".txt"}

    def __init__(self, knowledge_dir: str | Path, cleaner: TextCleaner | None = None) -> None:
        self.knowledge_dir = Path(knowledge_dir)
        self.cleaner = cleaner or TextCleaner()

    def load(self) -> list[KnowledgeDocument]:
        if not self.knowledge_dir.exists():
            return []

        documents: list[KnowledgeDocument] = []
        for path in sorted(self.knowledge_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in self.supported_suffixes:
                continue
            raw_text = path.read_text(encoding="utf-8")
            content = self.cleaner.clean(raw_text)
            if not content:
                continue
            doc_id = path.stem.replace(" ", "_")
            title = self._extract_title(content, path)
            documents.append(
                KnowledgeDocument(
                    doc_id=doc_id,
                    title=title,
                    content=content,
                    source=str(path.as_posix()),
                    metadata={
                        "filename": path.name,
                        "suffix": path.suffix.lower(),
                    },
                )
            )
        return documents

    def _extract_title(self, content: str, path: Path) -> str:
        for line in content.splitlines():
            if line.startswith("#"):
                return line.lstrip("#").strip()
        return path.stem.replace("_", " ")

