"""LLM 接入层。

把真实模型和 mock fallback 放在独立包中，是为了让 agent/router 只依赖统一边界，
后续替换 qwen-plus、OpenAI-compatible 或本地模型时不影响业务编排代码。
"""
