from dataclasses import dataclass, field


@dataclass(frozen=True)
class KnowledgeDocument:
    """原始知识文档对象，统一 loader 输出，避免后续检索链路依赖文件格式。"""

    doc_id: str
    title: str
    content: str
    source: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeChunk:
    """检索使用的最小文本单元，metadata 用于把答案追溯回原始文档和章节。"""

    doc_id: str
    chunk_id: str
    title: str
    content: str
    source: str
    section: str
    metadata: dict[str, str] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, str]:
        return {
            "doc_id": self.doc_id,
            "chunk_id": self.chunk_id,
            "title": self.title,
            "source": self.source,
            "section": self.section,
            **self.metadata,
        }
