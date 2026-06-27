import re

from app.rag.document import KnowledgeChunk, KnowledgeDocument


class ChineseTextSplitter:
    """面向中文客服知识库的轻量分块器。

    这里没有直接套 LangChain 默认 RecursiveCharacterTextSplitter，是因为默认分隔符
    和 keep_separator 行为可能把标题、标点留在相邻 chunk 的边界上，导致来源章节不清晰。
    本阶段先按 Markdown 标题和中文句末标点切分，并显式保留 section metadata。
    """

    _heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")
    _sentence_pattern = re.compile(r"(?<=[。！？；])")

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 80) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = max(0, min(chunk_overlap, chunk_size // 2))

    def split_documents(self, documents: list[KnowledgeDocument]) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        for document in documents:
            chunks.extend(self.split_document(document))
        return chunks

    def split_document(self, document: KnowledgeDocument) -> list[KnowledgeChunk]:
        sections = self._split_sections(document)
        chunks: list[KnowledgeChunk] = []
        chunk_index = 1
        for section, text in sections:
            for content in self._split_text(text):
                chunks.append(
                    KnowledgeChunk(
                        doc_id=document.doc_id,
                        chunk_id=f"{document.doc_id}-{chunk_index:04d}",
                        title=document.title,
                        content=content,
                        source=document.source,
                        section=section,
                        metadata=document.metadata,
                    )
                )
                chunk_index += 1
        return chunks

    def _split_sections(self, document: KnowledgeDocument) -> list[tuple[str, str]]:
        current_section = document.title
        current_lines: list[str] = []
        sections: list[tuple[str, str]] = []
        for line in document.content.splitlines():
            heading = self._heading_pattern.match(line)
            if heading:
                if current_lines:
                    sections.append((current_section, "\n".join(current_lines).strip()))
                current_section = heading.group(2).strip()
                current_lines = []
                continue
            if line.strip():
                current_lines.append(line.strip())
        if current_lines:
            sections.append((current_section, "\n".join(current_lines).strip()))
        return sections or [(document.title, document.content)]

    def _split_text(self, text: str) -> list[str]:
        paragraphs = [item.strip() for item in text.split("\n") if item.strip()]
        sentences: list[str] = []
        for paragraph in paragraphs:
            parts = [item.strip() for item in self._sentence_pattern.split(paragraph) if item.strip()]
            sentences.extend(parts or [paragraph])

        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            if not current:
                current = sentence
                continue
            if len(current) + len(sentence) <= self.chunk_size:
                current += sentence
                continue
            chunks.append(current)
            overlap = current[-self.chunk_overlap :] if self.chunk_overlap else ""
            current = f"{overlap}{sentence}"
        if current:
            chunks.append(current)
        return chunks

