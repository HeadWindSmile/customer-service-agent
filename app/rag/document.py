from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeDocument:
    """统一文档对象，提前稳定 RAG 输入输出边界。"""

    doc_id: str
    title: str
    content: str

