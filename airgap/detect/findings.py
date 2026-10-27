"""Finding model, marker matching, and severity scoring."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Iterable


class Severity:
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    ORDER = {CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3}


@dataclass
class Finding:
    id: str
    rule: str  # R1 | R2 | R3
    title: str
    severity: str
    asset_urn: str
    asset_name: str
    leaked_fields: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    blast_radius: int = 0
    consumers: dict[str, int] = field(default_factory=dict)
    remediation: str = ""
    explanation: str = ""  # filled in by the local LLM layer

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule": self.rule,
            "title": self.title,
            "severity": self.severity,
            "asset_urn": self.asset_urn,
            "asset_name": self.asset_name,
            "leaked_fields": self.leaked_fields,
            "evidence": self.evidence,
            "blast_radius": self.blast_radius,
            "consumers": self.consumers,
            "remediation": self.remediation,
            "explanation": self.explanation,
        }


def _fold(marker: str) -> str:
    """Caseless form of a marker, used on both sides of every comparison.

    str.casefold() alone is not enough for Turkish: 'İ' (U+0130) folds to 'i'
    plus a combining dot above (U+0307), so 'KİŞİSEL' would not equal
    'kişisel'. The dot is dropped after an 'i', and the dotless 'ı' is folded
    to 'i' as well, so 'KISITLI' typed on a non-Turkish keyboard still matches
    'Kısıtlı'. NFC keeps precomposed and decomposed input equal.
    """
    folded = unicodedata.normalize("NFC", marker.strip().casefold())
    return folded.replace("i\u0307", "i").replace("\u0131", "i")


def normalize_markers(markers: Iterable[str]) -> set[str]:
    """Case-fold markers and also expose the last dotted segment.

    'Classification.Sensitive' -> {'classification.sensitive', 'sensitive'}
    'KİŞİSEL' and 'Kişisel' -> {'kisisel'}
    """
    out: set[str] = set()
    for m in markers:
        low = _fold(m)
        if not low:
            continue
        out.add(low)
        if "." in low:
            out.add(low.rsplit(".", 1)[-1])
    return out


def is_sensitive(markers: Iterable[str], pii_set: set[str]) -> bool:
    return bool(normalize_markers(markers) & pii_set)


def score_severity(
    blast_radius: int,
    consumers: dict[str, int],
    human_facing_types: Iterable[str],
    critical_blast: int,
    high_blast: int,
) -> str:
    human = sum(consumers.get(t, 0) for t in human_facing_types)
    if human >= 1 or blast_radius >= critical_blast:
        return Severity.CRITICAL
    if blast_radius >= high_blast:
        return Severity.HIGH
    return Severity.MEDIUM


def sort_key(f: Finding) -> tuple:
    return (Severity.ORDER.get(f.severity, 9), -f.blast_radius, f.id)
