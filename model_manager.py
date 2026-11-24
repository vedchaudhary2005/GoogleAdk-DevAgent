import os
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
import litellm

# Silence litellm noisy telemetry logs
litellm.telemetry = False

load_dotenv()
logger = logging.getLogger("model_manager")

# Master catalog of supported models per provider
MODEL_CATALOG = {
    "groq": {
        "name": "Groq",
        "env_key": "GROQ_API_KEY",
        "models": [
            {
                "id": "groq/openai/gpt-oss-120b",
                "name": "GPT-OSS 120B",
                "tag": "Recommended",
                "description": "High capability 120B open model on Groq LPU"
            },
            {
                "id": "groq/openai/gpt-oss-20b",
                "name": "GPT-OSS 20B",
                "tag": "Fast",
                "description": "Fast 20B open model for rapid coding"
            },
            {
                "id": "groq/qwen/qwen3.8-27b",
                "name": "Qwen 3.8 27B",
                "tag": "Coding",
                "description": "27B parameter coding model"
            }
        ]
    },
    "mistral": {
        "name": "Mistral AI",
        "env_key": "MISTRAL_API_KEY",
        "models": [
            {
                "id": "mistral/codestral-latest",
                "name": "Codestral Latest",
                "tag": "Coding Specialist",
                "description": "Mistral's flagship code generation model"
            },
            {
                "id": "mistral/mistral-small-latest",
                "name": "Mistral Small",
                "tag": "Fast",
                "description": "Lightweight and responsive model"
            },
            {
                "id": "mistral/mistral-large-latest",
                "name": "Mistral Large",
                "tag": "Reasoning",
                "description": "Top-tier general reasoning and architecture model (Paid tiers)"
            }
        ]
    },
    "google": {
        "name": "Google Gemini",
        "env_key": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "models": [
            {
                "id": "gemini/gemini-2.5-flash",
                "name": "Gemini 2.5 Flash",
                "tag": "Fast & Smart",
                "description": "Next-gen multimodal model with massive context"
            },
            {
                "id": "gemini/gemini-2.5-pro",
                "name": "Gemini 2.5 Pro",
                "tag": "Advanced Reasoning",
                "description": "Deep thinking and complex code architecture"
            }
        ]
    },
    "openai": {
        "name": "OpenAI",
        "env_key": "OPENAI_API_KEY",
        "models": [
            {
                "id": "openai/gpt-4o",
                "name": "GPT-4o",
                "tag": "Flagship",
                "description": "OpenAI flagship omni model"
            },
            {
                "id": "openai/gpt-4o-mini",
                "name": "GPT-4o Mini",
                "tag": "Fast",
                "description": "Lightweight fast assistant"
            }
        ]
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "env_key": "ANTHROPIC_API_KEY",
        "models": [
            {
                "id": "anthropic/claude-3-5-sonnet-20241022",
                "name": "Claude 3.5 Sonnet",
                "tag": "Top Coder",
                "description": "State-of-the-art coding and reasoning benchmark"
            },
            {
                "id": "anthropic/claude-3-5-haiku-20241022",
                "name": "Claude 3.5 Haiku",
                "tag": "Fast",
                "description": "Fast and lightweight Claude assistant"
            }
        ]
    }
}


def is_provider_configured(provider_key: str) -> bool:
    """Check if API key for a provider is configured in environment."""
    provider_info = MODEL_CATALOG.get(provider_key)
    if not provider_info:
        return False
    env_keys = provider_info["env_key"]
    if isinstance(env_keys, str):
        env_keys = [env_keys]
    return any(bool(os.getenv(k)) for k in env_keys)


def get_configured_providers() -> List[Dict[str, Any]]:
    """Return all providers that have valid API keys in the environment."""
    load_dotenv(override=True)
    configured = []
    for p_id, p_info in MODEL_CATALOG.items():
        if is_provider_configured(p_id):
            configured.append({
                "id": p_id,
                "name": p_info["name"],
                "models": p_info["models"]
            })
    return configured


def get_all_configured_model_ids() -> List[str]:
    """Return a flat list of all model IDs that have active API keys."""
    model_ids = []
    for p in get_configured_providers():
        for m in p["models"]:
            model_ids.append(m["id"])
    return model_ids


def get_default_model() -> str:
    """Determine the default model based on configured providers and .env."""
    configured_ids = get_all_configured_model_ids()
    env_model = os.getenv("MODEL_NAME")
    if env_model and env_model in configured_ids:
        return env_model
    if configured_ids:
        # Default priority: Groq 120b, then Mistral Codestral, then first available
        for preferred in ["groq/openai/gpt-oss-120b", "mistral/codestral-latest", "groq/openai/gpt-oss-20b"]:
            if preferred in configured_ids:
                return preferred
        return configured_ids[0]
    return "groq/openai/gpt-oss-120b"


def get_fallback_chain(selected_model: str) -> List[str]:
    """
    Construct an ordered list of fallback models starting with selected_model,
    followed by alternative models from configured providers.
    """
    configured_ids = get_all_configured_model_ids()
    chain = []

    if selected_model in configured_ids:
        chain.append(selected_model)
    elif selected_model:
        chain.append(selected_model)

    # Preferred fallback order
    priority_order = [
        "groq/openai/gpt-oss-120b",
        "mistral/codestral-latest",
        "groq/openai/gpt-oss-20b",
        "mistral/mistral-small-latest",
        "groq/qwen/qwen3.8-27b",
        "gemini/gemini-2.5-flash",
        "openai/gpt-4o",
        "anthropic/claude-3-5-sonnet-20241022",
        "mistral/mistral-large-latest"
    ]

    for m in priority_order:
        if m in configured_ids and m not in chain:
            chain.append(m)

    # Any remaining configured models
    for m in configured_ids:
        if m not in chain:
            chain.append(m)

    return chain


def is_rate_limit_error(exception: Exception) -> bool:
    """Check if an exception indicates a rate limit, quota exhaustion, or temporary provider issue."""
    msg = str(exception).lower()
    exc_type = type(exception).__name__.lower()
    return any(term in msg or term in exc_type for term in [
        "rate_limit", "ratelimit", "429", "quota", "too many requests",
        "tokens per minute", "otpm", "itpm", "exceeded your current quota",
        "tier_not_allowed", "not available in your subscription tier",
        "service unavailable", "overloaded", "capacity", "503", "504"
    ])
