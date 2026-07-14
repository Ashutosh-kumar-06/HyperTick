"""Unified LLM factory — OpenAI and Gemini providers."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from swarm_orchestrator.config import Settings


def create_llm(settings: Settings) -> BaseChatModel:
    provider = settings.llm_provider.lower().strip()

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        return ChatGoogleGenerativeAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            google_api_key=settings.gemini_api_key,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            api_key=settings.openai_api_key,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq

        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        return ChatGroq(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            api_key=settings.groq_api_key,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}. Use 'openai', 'gemini', or 'groq'.")
