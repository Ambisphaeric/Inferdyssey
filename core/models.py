"""Fetch available models from OpenRouter and manage favorites."""

import json
from dataclasses import dataclass
from pathlib import Path

import requests

MODELS_CACHE = Path("experiments/.models_cache.json")

# Default favorites — pinned at the top of every model selector
FAVORITES = [
    "minimax/minimax-m2.5",
    "x-ai/grok-4.1-fast",
    "google/gemini-3.1-pro-preview",
    "anthropic/claude-opus-4.6"
]


@dataclass
class ModelInfo:
    id: str
    name: str
    pricing_prompt: float  # per 1M tokens
    pricing_completion: float
    context_length: int
    is_favorite: bool = False


def fetch_models(use_cache: bool = True) -> list[ModelInfo]:
    """Fetch all available models from OpenRouter. Caches to disk."""
    # Try cache first
    if use_cache and MODELS_CACHE.exists():
        try:
            data = json.loads(MODELS_CACHE.read_text())
            return _parse_models(data)
        except Exception:
            pass

    # Fetch from API (no auth needed)
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        # Cache it
        MODELS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        MODELS_CACHE.write_text(json.dumps(data))

        return _parse_models(data)
    except Exception:
        # Fallback to favorites only
        return [
            ModelInfo(id=f, name=f, pricing_prompt=0, pricing_completion=0,
                      context_length=0, is_favorite=True)
            for f in FAVORITES
        ]


def _parse_models(data: list[dict]) -> list[ModelInfo]:
    """Parse raw API data into ModelInfo list with favorites first."""
    models = []
    seen_ids = set()

    for m in data:
        mid = m.get("id", "")
        if not mid or mid in seen_ids:
            continue
        seen_ids.add(mid)

        pricing = m.get("pricing", {})
        prompt_price = float(pricing.get("prompt", "0") or "0")
        completion_price = float(pricing.get("completion", "0") or "0")

        models.append(ModelInfo(
            id=mid,
            name=m.get("name", mid),
            pricing_prompt=prompt_price * 1_000_000,
            pricing_completion=completion_price * 1_000_000,
            context_length=m.get("context_length", 0),
            is_favorite=mid in FAVORITES,
        ))

    # Sort: favorites first (in FAVORITES order), then alphabetical
    fav_order = {f: i for i, f in enumerate(FAVORITES)}
    favorites = sorted(
        [m for m in models if m.is_favorite],
        key=lambda m: fav_order.get(m.id, 999),
    )
    # Add any favorites not found in API (might be new/renamed)
    found_ids = {m.id for m in models}
    for fav_id in FAVORITES:
        if fav_id not in found_ids:
            favorites.append(ModelInfo(
                id=fav_id, name=fav_id, pricing_prompt=0,
                pricing_completion=0, context_length=0, is_favorite=True,
            ))

    rest = sorted(
        [m for m in models if not m.is_favorite],
        key=lambda m: m.id,
    )
    return favorites + rest


def get_model_options() -> list[str]:
    """Get model IDs suitable for a selectbox, favorites first."""
    models = fetch_models()
    return [m.id for m in models]


def get_model_display(models: list[ModelInfo]) -> dict[str, str]:
    """Map model ID to display string for selectbox format_func."""
    display = {}
    for m in models:
        prefix = "★ " if m.is_favorite else ""
        price = ""
        if m.pricing_prompt > 0:
            price = f" (${m.pricing_prompt:.2f}/M in)"
        elif m.is_favorite:
            price = ""
        display[m.id] = f"{prefix}{m.name}{price}"
    return display
