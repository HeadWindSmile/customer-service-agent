from pathlib import Path

from app.config import settings
from app.rag.document import KnowledgeDocument
from app.rag.vector_store import MockVectorStore
from app.schemas.chat import Source


class MockKnowledgeRetriever:
    """mock 检索器保持 RAG 调用形态，第二阶段可替换为真实 loader/splitter/vector store。"""

    def __init__(self, knowledge_path: str | None = None) -> None:
        self.knowledge_path = Path(knowledge_path or settings.mock_knowledge_path)
        self.vector_store = MockVectorStore(self._load_documents())

    def search(self, query: str, top_k: int = 3) -> list[Source]:
        return self.vector_store.search(query, top_k)

    def _load_documents(self) -> list[KnowledgeDocument]:
        if self.knowledge_path.exists():
            return self._parse_markdown(self.knowledge_path.read_text(encoding="utf-8"))
        return [
            KnowledgeDocument("mock-faq-1", "套餐办理规则", "套餐变更通常次月生效，具体以业务系统办理结果为准。"),
            KnowledgeDocument("mock-faq-2", "账单说明", "账单包含套餐月费、增值业务费和超量费用。"),
            KnowledgeDocument("mock-faq-3", "故障排查", "网络故障可先重启光猫和路由器，再检查欠费与线路状态。"),
        ]

    def _parse_markdown(self, raw_text: str) -> list[KnowledgeDocument]:
        documents: list[KnowledgeDocument] = []
        current_title = "客服知识库"
        current_lines: list[str] = []
        doc_index = 1
        for line in raw_text.splitlines():
            if line.startswith("## "):
                if current_lines:
                    documents.append(
                        KnowledgeDocument(
                            doc_id=f"mock-doc-{doc_index}",
                            title=current_title,
                            content=" ".join(current_lines).strip(),
                        )
                    )
                    doc_index += 1
                current_title = line.replace("## ", "").strip()
                current_lines = []
            elif line.strip() and not line.startswith("#"):
                current_lines.append(line.strip())
        if current_lines:
            documents.append(
                KnowledgeDocument(
                    doc_id=f"mock-doc-{doc_index}",
                    title=current_title,
                    content=" ".join(current_lines).strip(),
                )
            )
        return documents

