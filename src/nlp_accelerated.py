"""Optional accelerated NLP plugin.

This module is intentionally conservative:
- Keeps existing NLP behavior as the source of truth.
- Uses CUDA acceleration (when available) only for lightweight intent scoring.
- Falls back safely to baseline NLP outputs.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.nlp_pipeline import APP_TO_INTENT_MAP, EXPLICIT_GAME_CONTEXT_TERMS, nlp_pipeline_fuzzy

try:
    import torch  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    torch = None


def _get_torch():
    if torch is None:
        raise RuntimeError("Torch is not available")
    return torch


INTENT_CODE_MAP = {
    "2d_design": "2D_DESIGN",
    "3d_design": "3D_DESIGN",
    "ai_development": "AI_DEVELOPMENT",
    "web_development": "WEB_DEVELOPMENT",
    "video_editor": "VIDEO_EDITOR",
    "multitasking": "MULTITASKING",
}

INTENT_PRIORITY = [
    "ai_development",
    "3d_design",
    "video_editor",
    "2d_design",
    "web_development",
    "multitasking",
]


def is_accelerated_nlp_available() -> bool:
    if torch is None:
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _contains_term_with_boundary(text: str, term: str) -> bool:
    return re.search(r"\b" + re.escape(term) + r"\b", text) is not None


def _score_intent_with_torch(query: str) -> Optional[str]:
    """Compute keyword-based intent score with tensor ops on CUDA.

    This keeps logic close to existing keyword intent strategy while using GPU
    tensors for aggregation. It is intentionally simple and deterministic.
    """
    if not is_accelerated_nlp_available():
        return None

    _torch = _get_torch()

    query_lower = query.lower()
    intent_names = list(APP_TO_INTENT_MAP.keys())
    scores = _torch.zeros(len(intent_names), dtype=_torch.float32, device="cuda")

    for idx, intent_name in enumerate(intent_names):
        keywords = APP_TO_INTENT_MAP.get(intent_name, [])
        # Weighted keyword hits, same idea as baseline:
        # multi-word match contributes 2, single-word contributes 1.
        weighted_hits = []
        for keyword in keywords:
            if _contains_term_with_boundary(query_lower, keyword.lower()):
                weighted_hits.append(2.0 if " " in keyword else 1.0)
        if weighted_hits:
            scores[idx] = _torch.tensor(weighted_hits, device="cuda", dtype=_torch.float32).sum()

    max_score = float(scores.max().item())
    if max_score <= 0:
        return None

    winners = [
        intent_names[i]
        for i in range(len(intent_names))
        if float(scores[i].item()) == max_score
    ]

    for preferred in INTENT_PRIORITY:
        if preferred in winners:
            return INTENT_CODE_MAP.get(preferred)

    return INTENT_CODE_MAP.get(winners[0])


def _detect_game_context_with_torch(query: str) -> bool:
    if not is_accelerated_nlp_available():
        return False

    _torch = _get_torch()

    query_lower = query.lower()
    hits = [
        1.0 if _contains_term_with_boundary(query_lower, term) else 0.0
        for term in EXPLICIT_GAME_CONTEXT_TERMS
    ]
    if not hits:
        return False
    hit_tensor = _torch.tensor(hits, device="cuda", dtype=_torch.float32)
    return bool(hit_tensor.max().item() > 0)


def nlp_pipeline_accelerated(
    user_query: str,
    game_list: List[str],
    laptop_list: List[str],
    laptop_brand_list: List[str],
    unique_keyword_game_map,
    game_abbreviations_kb,
    game_alt_titles_kb,
    series_abbreviations,
    bigram_unique_kb,
    brand_models_mapping,
) -> Dict[str, Any]:
    """Accelerated NLP wrapper with safe baseline behavior.

    Returns the same shape as `nlp_pipeline_fuzzy`, plus optional diagnostics.
    """
    baseline = nlp_pipeline_fuzzy(
        user_query,
        game_list,
        laptop_list,
        laptop_brand_list,
        unique_keyword_game_map,
        game_abbreviations_kb,
        game_alt_titles_kb,
        series_abbreviations,
        bigram_unique_kb,
        brand_models_mapping,
    )

    if not is_accelerated_nlp_available():
        baseline["accelerated_nlp"] = False
        return baseline

    accelerated_intent = _score_intent_with_torch(user_query)
    accelerated_game_context = _detect_game_context_with_torch(user_query)

    # Keep baseline as the primary source; only enrich low-confidence blanks.
    if baseline.get("app_intent") is None and accelerated_intent is not None:
        baseline["app_intent"] = accelerated_intent

    if not baseline.get("has_game_context", False) and accelerated_game_context:
        baseline["has_game_context"] = True

    baseline["accelerated_nlp"] = True
    baseline["accelerated_device"] = "cuda"
    return baseline
