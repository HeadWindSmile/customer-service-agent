from time import perf_counter


def elapsed_ms() -> float:
    """返回毫秒级单调时间戳，用于计算工具调用耗时。"""
    return perf_counter() * 1000

