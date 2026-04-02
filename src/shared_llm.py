"""Bridge to the shared stock-daily-report LLM client."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType


DEFAULT_SHARED_LLM_CLIENT = (
    Path(__file__).resolve().parents[2]
    / "stock-daily-report"
    / "common"
    / "llm_client.py"
)
DEFAULT_MODEL = "gpt-5.4"
DEFAULT_REASONING_EFFORT = "xhigh"

_SHARED_LLM_MODULE: ModuleType | None = None


def _resolve_shared_llm_client_path() -> Path:
    configured = os.getenv("SHARED_LLM_CLIENT_PATH", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_SHARED_LLM_CLIENT


def _load_shared_llm_module() -> ModuleType:
    global _SHARED_LLM_MODULE
    if _SHARED_LLM_MODULE is not None:
        return _SHARED_LLM_MODULE

    client_path = _resolve_shared_llm_client_path()
    spec = importlib.util.spec_from_file_location("shared_stock_llm_client", client_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared llm client from {client_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _SHARED_LLM_MODULE = module
    return module


def call_shared_llm(
    prompt: str,
    *,
    system_prompt: str | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    timeout: int = 120,
    base_url: str | None = None,
    api_key: str | None = None,
    reasoning_effort: str | None = None,
) -> str:
    module = _load_shared_llm_module()
    result = module.chat_completion(
        prompt,
        system_prompt=system_prompt,
        model=(model or DEFAULT_MODEL),
        temperature=temperature,
        timeout=timeout,
        base_url=(str(base_url).strip() or None) if base_url is not None else None,
        api_key=(str(api_key).strip() or None) if api_key is not None else None,
        reasoning_effort=(reasoning_effort or DEFAULT_REASONING_EFFORT),
    )
    if result is None:
        raise RuntimeError("All LLM fallbacks failed (GMN + OpenRouter #1 + OpenRouter #2)")
    return result
