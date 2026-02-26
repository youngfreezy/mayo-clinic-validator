"""
LLM factory — single source of truth for ChatOpenAI configuration.

All agent files should call create_agent_llm() instead of constructing
ChatOpenAI directly. Centralizes API key, model selection, timeout, and
tracing metadata.
"""

from langchain_openai import ChatOpenAI
from config.settings import settings


def create_agent_llm(
    agent_name: str,
    validation_id: str = "",
    model: str = "gpt-5.1",
    temperature: float = 0,
    json_mode: bool = True,
    request_timeout: float = 120.0,
) -> ChatOpenAI:
    model_kwargs = {}
    if json_mode:
        model_kwargs["response_format"] = {"type": "json_object"}

    return ChatOpenAI(
        model=model,
        temperature=temperature,
        openai_api_key=settings.OPENAI_API_KEY,
        model_kwargs=model_kwargs,
        request_timeout=request_timeout,
        tags=[f"{agent_name}-agent", model],
        metadata={"agent": agent_name, "validation_id": validation_id},
    )
