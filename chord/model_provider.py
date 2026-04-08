"""Helpers for OpenAI-compatible providers, defaulting to APIYI."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


DEFAULT_API_BASE = "https://api.apiyi.com/v1"
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"


def _load_repo_env():
    """Load repo-local .env once so users can keep APIYI config in a file."""
    if load_dotenv is None:
        return
    load_dotenv(ENV_PATH, override=False)


_load_repo_env()


def get_openai_api_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "")


def get_openai_base_url() -> str:
    return os.environ.get("OPENAI_BASE_URL") or os.environ.get("APIYI_BASE_URL") or DEFAULT_API_BASE


def get_provider_kwargs():
    kwargs = {"base_url": get_openai_base_url()}
    api_key = get_openai_api_key()
    if api_key:
        kwargs["api_key"] = api_key
    return kwargs


def create_chat_openai(model: str, temperature: float = 0, **kwargs):
    from langchain_openai.chat_models import ChatOpenAI

    provider_kwargs = get_provider_kwargs()
    provider_kwargs.update(kwargs)
    return ChatOpenAI(model=model, temperature=temperature, **provider_kwargs)


def create_llamaindex_openai(model: str, **kwargs):
    from llama_index.llms.openai import OpenAI

    provider_kwargs = get_provider_kwargs()
    if "base_url" in provider_kwargs and "api_base" not in provider_kwargs:
        provider_kwargs["api_base"] = provider_kwargs.pop("base_url")
    provider_kwargs.update(kwargs)
    return OpenAI(model=model, **provider_kwargs)
