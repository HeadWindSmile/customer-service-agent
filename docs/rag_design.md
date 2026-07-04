# RAG 设计说明

## 目标

RAG 层负责把客服政策文档转成可检索知识库，并在 FAQ、账单解释、套餐推荐、故障排查等场景中返回可追溯的 `sources`。设计重点是可运行、可解释、可替换，而不是在 Demo 阶段追求复杂向量库能力。

## 检索生成链路图

```mermaid
flowchart LR
    Docs["data/knowledge/*.md"] --> Loader["loader.py"]
    Loader --> Cleaner["cleaner.py"]
    Cleaner --> Splitter["splitter.py"]
    Splitter --> Embedding["embeddings.py Mock/BGE/OpenAI-compatible"]
    Embedding --> Store["vector_store.py Mock/Chroma/Milvus"]
    Store --> Candidate["多候选召回 candidate_count"]
    Candidate --> MMR["MMR 相关性 + 多样性筛选"]
    MMR --> Reranker["reranker.py Mock/BGE/OpenAI-compatible"]
    Reranker --> Sources["sources TopK"]
    Sources --> Chain["rag_answer_chain.py LCEL"]
    Chain --> Answer["answer + sources"]
```

## 当前实现

| 能力 | 当前实现 |
|---|---|
| 文档来源 | `data/knowledge/` 下 Markdown/TXT |
| 文档清洗 | `TextCleaner` 去除多余空白 |
| 分块 | `ChineseTextSplitter`，按 Markdown section 和中文句末零宽断言分块 |
| Embedding | 默认 `MockEmbedding`，可配置 DashScope/OpenAI-compatible/BGE provider |
| Vector Store | 默认 `MockVectorStore`，Chroma lazy import，Milvus 可配置真实适配 |
| 检索 | `KnowledgeRetriever.search()` 先召回 candidate_count，再 MMR/Reranker 输出 top_k sources |
| 生成 | `RagAnswerChain` 使用 LCEL：Prompt -> LLM -> StrOutputParser |
| 兜底 | sources 为空时不调用 LLM，直接建议转人工 |

## 第 14 阶段检索增强

第 14 阶段把基础 top_k 检索增强为“多候选召回 + MMR + Reranker”的两阶段结构：

1. VectorStore 按 `RAG_CANDIDATE_COUNT` 先召回更多候选。
2. `select_mmr_sources()` 使用 query embedding 和候选 embedding，在相关性和多样性之间平衡，减少同一 section 的重复 chunk。
3. `BaseReranker` 抽象负责最终重排，默认 `MockReranker`；可配置 `BGEReranker` 或 OpenAI-compatible rerank HTTP 网关。
4. trace 会记录 `vector_store_type`、`embedding_provider`、`candidate_count`、`mmr_enabled`、`reranker_used`、`reranker_type`、`final_top_k`。

这样做的原因是：生产 RAG 往往不是直接向量 top_k，而是先扩大召回，再通过多样性和 rerank 提升 TopK 命中质量；同时本地 Demo 不能强制依赖大型模型或向量库，所以所有真实接入点都必须有 fallback。

## sources 设计

接口响应中的每个 source 包含：

```text
doc_id, title, content, score, metadata
```

这样做的原因：

1. 面试演示时可以证明答案来自知识库，不是模型随口生成。
2. trace 中可以记录 `doc_ids`、`scores`、`source_count`。
3. 后续接真实向量库或 reranker 时，接口契约不用改。

第 14 阶段新增的 MMR/reranker 元信息会放在 `metadata` 中，例如 `mmr_rank`、`original_score`、`reranker_type`、`rerank_score`，不会改变接口顶层结构。

## LCEL 生成链路

`app/agents/chains/rag_answer_chain.py` 把检索资料、用户问题、会话上下文、summary 和 key_facts 拼入 Prompt，再通过 LCEL 管道生成回答。

关键约束：

1. 只能基于 sources 回答。
2. 不得编造资费、赔偿、办理承诺。
3. 具体金额、办理结果以业务系统返回为准。
4. 真实 LLM 失败时 fallback 到 `MockLLM`。

## RAG 缓存

第 11 阶段新增了轻量 TTL 缓存，只缓存公开知识库检索结果，不缓存套餐、账单、工单等敏感业务结果。trace 中会记录 `rag_cache_hit`，便于演示缓存是否命中。

## 生产扩展方式

当前 Demo 默认不接真实 Milvus、BGE 或 BGE-Reranker，但已经提供可配置适配。生产环境可以扩展为：

1. 使用企业文档同步任务更新知识库。
2. 使用真实 BGE 或企业 embedding 服务替换 MockEmbedding。
3. 使用 Milvus、PGVector 或企业向量库替换本地 store；Milvus 连接失败时 fallback 到 MockVectorStore。
4. 使用 BGE-Reranker 或企业 rerank 网关替换 MockReranker。
5. 把评测集扩展为持续回归评测。

这些都是可扩展方向，不代表当前 Demo 已完成真实生产级 RAG 平台。
