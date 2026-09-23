"""Scope-aware generalization (Master Prompt §17, §18).

Turns a cluster of episodes into a *scoped, provisional* candidate claim. The
claim text is generated deterministically from the shared pattern; it always
names its scope and evidence counts. Generalization beyond the observed scope is
refused, not silently implied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..domain.protac.context import ProtacContext, context_from_any
from ..domain.protac.evidence import EvidenceBundle
from ..util import normalize_text, slug, tokenize

_STOPWORDS = {
    "the", "and", "with", "for", "was", "were", "this", "that", "from", "into",
    "has", "have", "had", "not", "but", "are", "its", "our", "their", "due",
    "when", "then", "than", "also", "may", "might", "could", "would", "which",
    "observed", "prediction", "predicted", "outcome", "value", "error",
}

_SCOPE_FIELDS = (
    ("target_scope", "target_gene", "target_uniprot"),
    ("target_domain_scope", "target_domain", None),
    ("e3_scope", "e3_ligase", None),
    ("warhead_scope", "warhead_name", None),
    ("cell_scope", "cell_line", None),
    ("assay_scope", "assay_type", None),
    ("organism_scope", "organism", None),
)


@dataclass
class PatternSummary:
    descriptors: list[str] = field(default_factory=list)
    shared_interpretations: list[str] = field(default_factory=list)
    metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    n_episodes: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "descriptors": self.descriptors,
            "shared_interpretations": self.shared_interpretations,
            "metrics": self.metrics,
            "n_episodes": self.n_episodes,
        }


def episode_context(episode: dict[str, Any]) -> ProtacContext:
    return context_from_any(episode.get("context_json") or {})


def common_scope(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Scope = coordinates on which *all* episodes agree."""
    if not episodes:
        return {}
    contexts = [episode_context(e) for e in episodes]
    scope: dict[str, Any] = {}
    for scope_name, primary, secondary in _SCOPE_FIELDS:
        values = set()
        for ctx in contexts:
            value = getattr(ctx, primary, None) or (getattr(ctx, secondary, None) if secondary else None)
            values.add(normalize_text(value) if value else "")
        if len(values) == 1 and "" not in values:
            scope[scope_name] = next(v for v in (getattr(contexts[0], primary, None)
                                                 or (getattr(contexts[0], secondary, None) if secondary else None),)
                                     if v)
        else:
            scope[scope_name] = None
    # Mark whether the scope is broad (some coordinates differ).
    differing = [name for name, value in scope.items() if value is None]
    scope["_differing"] = differing
    return scope


def summarize_pattern(episodes: list[dict[str, Any]], min_share: float = 0.6) -> PatternSummary:
    n = len(episodes)
    if n == 0:
        return PatternSummary()
    token_counts: dict[str, int] = {}
    interpretations: list[str] = []
    metrics: dict[str, list[float]] = {}

    for ep in episodes:
        text = " ".join(str(ep.get(k) or "") for k in ("title", "content", "interpretation"))
        seen = set()
        for tok in tokenize(text):
            if tok in _STOPWORDS or len(tok) < 3:
                continue
            if tok in seen:
                continue
            seen.add(tok)
            token_counts[tok] = token_counts.get(tok, 0) + 1
        if ep.get("interpretation"):
            interpretations.append(str(ep["interpretation"]))
        observed = ep.get("observed_json") or {}
        for key, value in observed.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                metrics.setdefault(key, []).append(float(value))

    threshold = max(2, int(min_share * n))
    descriptors = sorted(
        (tok for tok, count in token_counts.items() if count >= threshold),
        key=lambda t: (-token_counts[t], t),
    )[:8]

    # shared interpretations = exact duplicates appearing more than once
    interp_counts: dict[str, int] = {}
    for text in interpretations:
        interp_counts[text] = interp_counts.get(text, 0) + 1
    shared_interps = [t for t, c in interp_counts.items() if c >= 2][:3]

    metric_summary: dict[str, dict[str, float]] = {}
    for key, values in metrics.items():
        if len(values) < 2:
            continue
        metric_summary[key] = {
            "n": float(len(values)),
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }
    return PatternSummary(
        descriptors=descriptors,
        shared_interpretations=shared_interps,
        metrics=metric_summary,
        n_episodes=n,
    )


def scope_text(scope: dict[str, Any]) -> str:
    parts = [f"{k.replace('_scope','')}={v}" for k, v in scope.items()
             if v and not k.startswith("_")]
    return " + ".join(parts) if parts else "unspecified scope"


def build_claim(
    episodes: list[dict[str, Any]],
    scope: dict[str, Any],
    summary: PatternSummary,
    evidence: EvidenceBundle,
) -> str:
    n = summary.n_episodes
    scope_str = scope_text(scope)
    if summary.shared_interpretations:
        pattern = summary.shared_interpretations[0]
    elif summary.descriptors:
        pattern = "recurring co-occurrence of " + ", ".join(summary.descriptors[:5])
    else:
        pattern = "a recurring observational pattern"

    metric_bits = []
    for key, stats in sorted(summary.metrics.items()):
        metric_bits.append(f"{key}: mean={stats['mean']:.2f} (n={int(stats['n'])})")
    metrics_str = "; ".join(metric_bits)

    return (
        f"Across {n} in-scope observations [{scope_str}], {pattern} was repeatedly "
        f"associated with the observed outcomes. "
        f"Support: {evidence.n_supporting} episode(s) / {evidence.independent_sources()} "
        f"independent source(s); contradictions: {evidence.n_contradicting}. "
        + (f"Observed metrics — {metrics_str}. " if metrics_str else "")
        + "This claim is provisional and bounded to the stated scope."
    )


def topic_key_for(scope: dict[str, Any], summary: PatternSummary) -> str:
    target = scope.get("target_scope") or "any"
    e3 = scope.get("e3_scope") or "any"
    if summary.shared_interpretations:
        descriptor = slug(summary.shared_interpretations[0])[:40]
    elif summary.descriptors:
        descriptor = "-".join(summary.descriptors[:3])
    else:
        descriptor = "general"
    return f"topic:{slug(str(target))}:{slug(str(e3))}:{slug(descriptor)}"[:180]


def scope_is_anchored(scope: dict[str, Any]) -> bool:
    """A generalization must be anchored to at least a target or an E3."""
    return bool(scope.get("target_scope") or scope.get("e3_scope"))
