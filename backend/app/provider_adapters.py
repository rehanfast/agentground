"""
backend/app/provider_adapters.py
Unified LLM factory for all supported providers.

Supported providers and their quirks:
  openai    — standard; uses ChatOpenAI
  deepseek  — OpenAI-compatible; reasoning tokens in <think> blocks stripped
  xai       — OpenAI-compatible (api.x.ai/v1); Grok models
  google    — Gemini; uses ChatGoogleGenerativeAI (NOT ChatOpenAI)
  ollama    — local OpenAI-compatible; dummy key
  other     — any OpenAI-compatible endpoint

.env keys consumed:
  OPENAI_API_KEY       = sk-...       (multiple: OPENAI_API_KEY_2, _3, …)
  GOOGLE_API_KEY       = AIza...      (multiple: GOOGLE_API_KEY_2, …)
  XAI_API_KEY          = xai-...      (multiple: XAI_API_KEY_2, …)
  DEEPSEEK_API_KEY     = sk-...       (multiple: DEEPSEEK_API_KEY_2, …)

Multi-key convention: PROVIDER_API_KEY, PROVIDER_API_KEY_2, PROVIDER_API_KEY_3, …
All non-empty variants are collected into a key pool for rotation.
"""

from __future__ import annotations

import os
import re
import threading
from langchain_core.messages import BaseMessage, AIMessage

try:
    from backend.app.resource_callback import AgentStopException
except ImportError:
    class AgentStopException(Exception): pass


# ── Reasoning-token stripper (DeepSeek-R1, QwQ, etc.) ───────────────────────

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """Remove <think>…</think> reasoning segments from model output."""
    return _THINK_RE.sub("", text).strip()


# ── .env key pool loader ──────────────────────────────────────────────────────

PROVIDER_ENV_PREFIXES: dict[str, str] = {
    "openai":        "OPENAI_API_KEY",
    "google":        "GOOGLE_API_KEY",
    "google_openai": "GOOGLE_API_KEY",
    "groq":          "GROQ_API_KEY",
    "xai":           "XAI_API_KEY",
    "deepseek":      "DEEPSEEK_API_KEY",
}

PROVIDER_BASE_URLS: dict[str, str] = {
    "openai":   "https://api.openai.com/v1",
    "google":   "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq":     "https://api.groq.com/openai/v1",
    "xai":      "https://api.x.ai/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "ollama":   "http://localhost:11434/v1",
}


def _looks_like_env_var(s: str) -> bool:
    """Return True if s is an env var name (UPPERCASE_WITH_UNDERSCORES, no spaces)."""
    import re
    return bool(re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", s.strip()))


def resolve_key(raw: str) -> str:
    """
    If raw looks like an env var name (e.g. "GOOGLE_API_KEY"), resolve it via os.getenv().
    Otherwise return raw as-is (it is the actual key value).
    """
    raw = raw.strip()
    if _looks_like_env_var(raw):
        return os.getenv(raw, "").strip()
    return raw


def load_env_keys(provider: str) -> list[str]:
    """
    Load all API keys for a provider from environment variables.
    Checks PROVIDER_API_KEY, PROVIDER_API_KEY_2, … up to 10.
    Returns deduplicated non-empty list.
    """
    prefix = PROVIDER_ENV_PREFIXES.get(provider, f"{provider.upper()}_API_KEY")
    keys: list[str] = []
    k = os.getenv(prefix, "").strip()
    if k: keys.append(k)
    for i in range(2, 11):
        k = os.getenv(f"{prefix}_{i}", "").strip()
        if k: keys.append(k)
    seen = set()
    result = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            result.append(k)
    return result


def resolve_keys_list(raw_keys: list[str], provider: str) -> list[str]:
    """
    Resolve a list of stored keys (which may be actual key values or env var names).
    Falls back to load_env_keys(provider) if the resolved list is empty.
    """
    resolved = [resolve_key(k) for k in raw_keys]
    resolved = [k for k in resolved if k]
    if not resolved:
        resolved = load_env_keys(provider)
    return resolved


def detect_provider(api_url: str, model_id: str = "") -> str:
    """Infer provider from URL or model_id."""
    url = api_url.lower()
    
    # Groq — must check before generic OpenAI catch-all
    if "groq.com" in url:
        return "groq"
    # If URL explicitly endpoints at /openai/ or contains openai.com, it's OpenAI compatible
    if "googleapis.com" in url and "openai" in url.split("/")[-2:]:
        return "google_openai"
    elif "openai" in url.split("/")[-2:] or "openai.com" in url:
        return "openai"
        
    if any(h in url for h in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "11434")):
        return "ollama"
    if "googleapis.com" in url or "google" in url:
        return "google"
    if "x.ai" in url or "grok" in model_id.lower():
        return "xai"
    if "deepseek" in url or "deepseek" in model_id.lower():
        return "deepseek"
    return "other"


# ── LLM factory ───────────────────────────────────────────────────────────────

def make_llm(
    provider:   str,
    api_url:    str,
    model_name: str,
    api_key:    str,
    temperature: float = 0.0,
):
    from langchain_openai import ChatOpenAI
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_community.chat_models import ChatOllama
    
    provider = provider.lower()
    
    # Strip provider prefixes for direct APIs to prevent 404 errors
    # (Proxies like OpenRouter expect the prefix, so we don't strip if provider is "other")
    if provider in ("google", "google_openai") and model_name.lower().startswith("google/"):
        model_name = model_name[7:]
    elif provider == "openai" and model_name.lower().startswith("openai/"):
        model_name = model_name[7:]
    elif provider == "deepseek" and model_name.lower().startswith("deepseek/"):
        model_name = model_name[9:]
    elif provider == "xai" and model_name.lower().startswith("xai/"):
        model_name = model_name[4:]
    
    if provider == "google":
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temperature,
            max_retries=0, # Let Auto Mode handle retries
        )
    elif provider == "ollama":
        return ChatOllama(
            base_url=api_url,
            model=model_name,
            temperature=temperature,
            max_retries=0,
        )
    else:
        # openai, xai, deepseek, google_openai, or other (assumes OpenAI compatible)
        # Deepseek and xAI both offer OpenAI compatible endpoints.
        return ChatOpenAI(
            api_key=api_key,
            base_url=api_url if api_url else None,
            model=model_name,
            temperature=temperature,
            max_retries=0,
        )


def invoke_llm(llm, messages: list[BaseMessage], stop_event: threading.Event | None = None) -> str:
    """
    Invoke a LangChain LLM and return cleaned text content.
    Strips reasoning tokens for models that emit them.
    """
    if stop_event and stop_event.is_set():
        raise AgentStopException("Stopped by user.")

    response = llm.invoke(messages)
    content = ""
    if hasattr(response, "content"):
        content = response.content or ""
    elif isinstance(response, str):
        content = response

    # Handle multi-modal or chunked lists (Gemini, etc.)
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, str):
                texts.append(block)
            elif isinstance(block, dict):
                if "text" in block:
                    texts.append(block["text"])
                elif "thinking" in block:
                    pass
        content = "".join(texts)
    
    if not isinstance(content, str):
        content = str(content)

    # Strip <think> blocks emitted by DeepSeek-R1, QwQ, etc.
    if "<think>" in content:
        content = strip_reasoning(content)

    return content.strip()
