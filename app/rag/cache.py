import hashlib
from collections import OrderedDict
from time import monotonic

from app.config import settings
from app.schemas.chat import Source


class RagSearchCache:
    """RAG 检索结果的轻量 TTL 缓存。

    这里仅缓存公开知识库 sources，不缓存用户套餐、账单、工单等敏感业务结果，避免
    引入跨用户隔离和变更失效问题。
    """

    def __init__(self, ttl_seconds: int | None = None, max_size: int | None = None) -> None:
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else settings.rag_cache_ttl_seconds
        self.max_size = max(1, max_size or settings.rag_cache_max_size)
        self._items: OrderedDict[str, tuple[float, list[Source]]] = OrderedDict()

    def get(self, query: str, top_k: int, variant: str = "") -> list[Source] | None:
        if self.ttl_seconds <= 0:
            return None
        key = self._key(query, top_k, variant)
        item = self._items.get(key)
        if item is None:
            return None
        expires_at, sources = item
        if expires_at < monotonic():
            self._items.pop(key, None)
            return None
        self._items.move_to_end(key)
        return [source.model_copy(deep=True) for source in sources]

    def set(self, query: str, top_k: int, sources: list[Source], variant: str = "") -> None:
        if self.ttl_seconds <= 0:
            return
        key = self._key(query, top_k, variant)
        self._items[key] = (monotonic() + self.ttl_seconds, [source.model_copy(deep=True) for source in sources])
        self._items.move_to_end(key)
        while len(self._items) > self.max_size:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()

    def _key(self, query: str, top_k: int, variant: str = "") -> str:
        normalized = " ".join(query.strip().lower().split())
        cache_input = f"{normalized}|{variant}"
        digest = hashlib.sha256(cache_input.encode("utf-8")).hexdigest()
        return f"{digest}:{top_k}"


rag_search_cache = RagSearchCache()
