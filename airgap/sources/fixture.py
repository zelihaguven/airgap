"""Load a synthetic DataHub-shape metadata graph from a JSON fixture.

The fixture uses the exact same field names and lineage model as real DataHub
metadata, so the detection engine cannot tell the difference between this and a
live instance.

With no path, the synthetic Acme catalog bundled in `airgap/data/` is used.
"""
from __future__ import annotations

import json
import sys
from importlib import resources

from airgap.errors import AirgapError
from airgap.model import Asset, Field, FieldLineage, LineageEdge, MetadataGraph
from airgap.sources.base import MetadataSource

BUNDLED_FIXTURE = "acme_datalake.json"


class FixtureSource(MetadataSource):
    name = "fixture"

    def __init__(self, path: str | None = None) -> None:
        self.path = path or None

    def fetch(self) -> MetadataGraph:
        if self.path is None:
            bundled = resources.files("airgap.data").joinpath(BUNDLED_FIXTURE)
            raw = json.loads(bundled.read_text(encoding="utf-8"))
        else:
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
            except FileNotFoundError:
                raise AirgapError(f"fixture file not found: {self.path}") from None
            except json.JSONDecodeError as exc:
                raise AirgapError(
                    f"fixture file {self.path} is not valid JSON: {exc}"
                ) from None
        try:
            return _build_graph(raw)
        except KeyError as exc:
            raise AirgapError(
                f"fixture file {self.path or BUNDLED_FIXTURE}: an entry is missing "
                f"the required key {exc.args[0]!r}"
            ) from None


def _build_graph(raw: dict) -> MetadataGraph:
    graph = MetadataGraph()
    for a in _merge_duplicate_assets(raw.get("assets", [])):
        fields = tuple(
            Field(
                path=f["path"],
                native_type=f.get("native_type", ""),
                tags=tuple(f.get("tags", [])),
                glossary_terms=tuple(f.get("glossary_terms", [])),
            )
            for f in a.get("fields", [])
        )
        graph.add_asset(
            Asset(
                urn=a["urn"],
                name=a["name"],
                entity_type=a.get("entity_type", "dataset"),
                platform=a.get("platform", ""),
                tags=tuple(a.get("tags", [])),
                owners=tuple(a.get("owners", [])),
                fields=fields,
            )
        )

    graph.edges = [
        LineageEdge(upstream=e["upstream"], downstream=e["downstream"])
        for e in raw.get("edges", [])
    ]
    graph.field_edges = [
        FieldLineage(
            up_urn=fe["up_urn"],
            up_field=fe["up_field"],
            down_urn=fe["down_urn"],
            down_field=fe["down_field"],
        )
        for fe in raw.get("field_edges", [])
    ]
    return graph


def _union(*lists: list) -> list:
    """Concatenate lists, dropping repeats and keeping first-seen order."""
    out: list = []
    for items in lists:
        for item in items:
            if item not in out:
                out.append(item)
    return out


def _merge_duplicate_assets(assets: list[dict]) -> list[dict]:
    """Merge fixture entries that share a URN instead of keeping only the last.

    A URN identifies one entity, so repeated entries are read as partial views
    of it. Their tags, owners, fields and field-level tags and glossary terms
    are unioned, so no PII classification is ever dropped, and the result does
    not depend on the order of the entries. Name, entity type and platform come
    from the first entry. Each merged URN is reported on stderr, because a
    duplicate usually means a broken export.
    """
    merged: dict[str, dict] = {}
    counts: dict[str, int] = {}
    for a in assets:
        urn = a["urn"]
        counts[urn] = counts.get(urn, 0) + 1
        cur = merged.get(urn)
        if cur is None:
            merged[urn] = dict(a)
            continue
        cur["tags"] = _union(cur.get("tags", []), a.get("tags", []))
        cur["owners"] = _union(cur.get("owners", []), a.get("owners", []))
        by_path = {f["path"]: dict(f) for f in cur.get("fields", [])}
        for f in a.get("fields", []):
            old = by_path.get(f["path"])
            if old is None:
                by_path[f["path"]] = dict(f)
                continue
            old["native_type"] = old.get("native_type") or f.get("native_type", "")
            old["tags"] = _union(old.get("tags", []), f.get("tags", []))
            old["glossary_terms"] = _union(
                old.get("glossary_terms", []), f.get("glossary_terms", [])
            )
        cur["fields"] = list(by_path.values())
    for urn, n in counts.items():
        if n > 1:
            print(
                f"  ! Fixture lists {urn} {n} times; merged its tags, owners and "
                f"fields into one asset.",
                file=sys.stderr,
            )
    return list(merged.values())
