"""Detection settings: the config's `detection` block merged with the defaults.

The defaults are the `detection` block of the config bundled in
`airgap/data/config.yaml`, which is the documented example. A config that
leaves out the block, or leaves one of its keys out or empty, gets the default
for that part and a note saying so, instead of silently detecting nothing. An explicitly empty
`pii_markers` list cannot match anything, so it is rejected.
"""
from __future__ import annotations

import copy
import re
from importlib import resources

import yaml

_KEYS = ("pii_markers", "human_facing_types", "severity")


def _validated_name_patterns(value: object) -> dict[str, str]:
    """`detection.name_patterns`: label -> regex, off when absent or empty."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise DetectionConfigError(
            "config key 'detection.name_patterns' must be a mapping of label to regex"
        )
    out: dict[str, str] = {}
    for label, pattern in value.items():
        if not isinstance(label, str) or not label.strip():
            raise DetectionConfigError(
                "config key 'detection.name_patterns' must use non-empty string labels"
            )
        if not isinstance(pattern, str) or not pattern.strip():
            raise DetectionConfigError(
                f"config key 'detection.name_patterns.{label}' must be a non-empty regex"
            )
        try:
            re.compile(pattern)
        except re.error as exc:
            raise DetectionConfigError(
                f"config key 'detection.name_patterns.{label}' is not a valid regex: {exc}"
            ) from None
        out[label.strip()] = pattern
    return out


class DetectionConfigError(ValueError):
    """The `detection` block of a config cannot be used."""


def _bundled_detection() -> dict:
    text = resources.files("airgap.data").joinpath("config.yaml").read_text(encoding="utf-8")
    return (yaml.safe_load(text) or {})["detection"]


def detection_settings(cfg: dict) -> tuple[dict, list[str]]:
    """Return the effective detection settings and notes about applied defaults.

    Raises DetectionConfigError when the block is not a mapping or when
    `pii_markers` is empty, blank, or not a list of strings.
    """
    defaults = _bundled_detection()
    raw = cfg.get("detection")
    notes: list[str] = []
    if raw is None:
        notes.append("config has no detection block; using the bundled detection defaults")
        return copy.deepcopy(defaults), notes
    if not isinstance(raw, dict):
        raise DetectionConfigError("config key 'detection' must be a mapping")

    det = dict(raw)
    for key in _KEYS:
        if det.get(key) is None:  # missing, or present with no value
            det[key] = copy.deepcopy(defaults[key])
            notes.append(f"config has no detection.{key}; using the bundled default")
    if not isinstance(det["severity"], dict):
        raise DetectionConfigError("config key 'detection.severity' must be a mapping")
    det["severity"] = {**defaults["severity"], **det["severity"]}
    if not isinstance(det["human_facing_types"], list):
        raise DetectionConfigError("config key 'detection.human_facing_types' must be a list")

    markers = det["pii_markers"]
    if not isinstance(markers, list) or not all(isinstance(m, str) for m in markers):
        raise DetectionConfigError("config key 'detection.pii_markers' must be a list of strings")
    if not any(m.strip() for m in markers):
        raise DetectionConfigError(
            "config key 'detection.pii_markers' is empty, so no field could ever be "
            "detected as PII; list at least one marker or remove the key to use the "
            "defaults"
        )
    det["name_patterns"] = _validated_name_patterns(det.get("name_patterns"))
    return det, notes
