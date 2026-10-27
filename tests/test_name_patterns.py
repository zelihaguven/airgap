"""R3: opt-in name-based PII candidates (#7).

Off by default; when on, a field whose dot-separated name segment fully matches
a configured regex is reported at LOW severity. It never becomes a lineage
origin for R1/R2.
"""
from __future__ import annotations

import pytest

from airgap.detect import run_rules
from airgap.detect.findings import Severity
from airgap.detect.settings import DetectionConfigError, detection_settings
from airgap.model import Asset, Field, FieldLineage, MetadataGraph

DS = "urn:li:dataset:(urn:li:dataPlatform:postgres,app.customers,PROD)"
DOWN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,wh.customers,PROD)"

EMAIL = "e?mail(_?address)?"


def _graph(*paths: str) -> MetadataGraph:
    graph = MetadataGraph()
    graph.add_asset(
        Asset(
            urn=DS,
            name="customers",
            platform="postgres",
            fields=tuple(Field(path=p) for p in paths),
        )
    )
    return graph


def _cfg(patterns: dict[str, str] | None = None) -> dict:
    det: dict = {"pii_markers": ["PII"]}
    if patterns is not None:
        det["name_patterns"] = patterns
    return {"detection": det}


def test_r3_is_off_by_default():
    assert run_rules(_graph("email"), _cfg()) == []


def test_an_untagged_email_column_is_one_low_finding():
    findings = run_rules(_graph("email"), _cfg({"email": EMAIL}))

    assert [(f.rule, f.severity, f.leaked_fields) for f in findings] == [
        ("R3", Severity.LOW, ["email"])
    ]
    assert findings[0].evidence == ["customers.email matches the 'email' name pattern."]
    assert findings[0].id == "AIRGAP-R3-001"


def test_matching_is_per_name_segment_not_a_prefix():
    # `email_opt_in_count` is a counter, not an address: a segment must match whole.
    assert run_rules(_graph("email_opt_in_count"), _cfg({"email": EMAIL})) == []

    # A qualified path matches on the `email` segment.
    findings = run_rules(_graph("profiles.email"), _cfg({"email": EMAIL}))
    assert [f.leaked_fields for f in findings] == [["profiles.email"]]


def test_the_first_matching_label_is_reported():
    findings = run_rules(
        _graph("ssn"), _cfg({"email": EMAIL, "national_id": "tckn|ssn"})
    )

    assert findings[0].leaked_fields == ["ssn"]
    assert findings[0].evidence == ["customers.ssn matches the 'national_id' name pattern."]


def test_r3_never_feeds_r1():
    graph = _graph("email", "email_copy")
    graph.add_asset(
        Asset(urn=DOWN, name="wh.customers", platform="snowflake", fields=(Field(path="email"),))
    )
    graph.field_edges.append(FieldLineage(DS, "email", DOWN, "email"))

    findings = run_rules(graph, _cfg({"email": EMAIL}))

    assert [f.rule for f in findings] == ["R3", "R3"]  # one per dataset, no R1
    assert [f.leaked_fields for f in findings] == [["email"], ["email"]]


@pytest.mark.parametrize(
    "patterns",
    [
        {"email": "("},
        {"email": ""},
        {"": EMAIL},
        {"email": 3},
        ["email"],
    ],
)
def test_unusable_name_patterns_are_rejected(patterns):
    with pytest.raises(DetectionConfigError):
        detection_settings({"detection": {"pii_markers": ["PII"], "name_patterns": patterns}})


def test_empty_name_patterns_mean_off():
    det, notes = detection_settings({"detection": {"pii_markers": ["PII"], "name_patterns": {}}})
    assert det["name_patterns"] == {}
    assert notes  # the missing keys still get their bundled defaults
