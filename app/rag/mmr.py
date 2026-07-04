import math

from app.rag.embeddings import BaseEmbedding
from app.schemas.chat import Source


def select_mmr_sources(
    query: str,
    candidates: list[Source],
    embedding: BaseEmbedding,
    top_k: int,
    lambda_mult: float = 0.7,
) -> list[Source]:
    """使用 MMR 在相关性和多样性之间做平衡。

    向量库先召回较多候选，MMR 再减少高度重复的 chunk。这里放在 RAG 层而不是
    VectorStore 层，是为了让 Mock/Chroma/Milvus 都复用同一套重排逻辑。
    """

    if top_k <= 0 or not candidates:
        return []
    if len(candidates) <= top_k:
        return [_with_mmr_metadata(source, rank=index + 1, query_score=source.score, diversity_score=0.0) for index, source in enumerate(candidates)]

    lambda_mult = max(0.0, min(lambda_mult, 1.0))
    query_vector = embedding.embed_query(query)
    candidate_vectors = embedding.embed_documents([_candidate_text(source) for source in candidates])
    query_scores = [_cosine_similarity(query_vector, vector) for vector in candidate_vectors]

    selected_indices: list[int] = []
    selected_diversity: dict[int, float] = {}
    remaining_indices = set(range(len(candidates)))
    while remaining_indices and len(selected_indices) < top_k:
        best_index = None
        best_score = float("-inf")
        best_diversity = 0.0
        for index in remaining_indices:
            diversity_penalty = 0.0
            if selected_indices:
                diversity_penalty = max(
                    _cosine_similarity(candidate_vectors[index], candidate_vectors[selected])
                    for selected in selected_indices
                )
            mmr_score = lambda_mult * query_scores[index] - (1 - lambda_mult) * diversity_penalty
            if mmr_score > best_score:
                best_index = index
                best_score = mmr_score
                best_diversity = diversity_penalty
        if best_index is None:
            break
        selected_indices.append(best_index)
        selected_diversity[best_index] = best_diversity
        remaining_indices.remove(best_index)

    results: list[Source] = []
    for rank, index in enumerate(selected_indices, start=1):
        results.append(
            _with_mmr_metadata(
                candidates[index],
                rank=rank,
                query_score=query_scores[index],
                diversity_score=selected_diversity.get(index, 0.0),
            )
        )
    return results


def _with_mmr_metadata(source: Source, rank: int, query_score: float, diversity_score: float) -> Source:
    metadata = {
        **source.metadata,
        "mmr_rank": rank,
        "mmr_query_score": round(query_score, 4),
        "mmr_diversity_score": round(diversity_score, 4),
    }
    return source.model_copy(update={"metadata": metadata})


def _candidate_text(source: Source) -> str:
    section = str(source.metadata.get("section", ""))
    return f"{source.title}\n{section}\n{source.content}"


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return numerator / (left_norm * right_norm)
