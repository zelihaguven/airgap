"""Seed a local DataHub Lite instance from the Acme fixture.

Converts the fixture into real DataHub metadata aspects (schema with field-level
tags & glossary terms, ownership, dataset + column-level lineage, dashboards and
charts) and writes them to a metadata file that `datahub lite import` ingests.

This proves Airgap runs against genuine DataHub metadata — no Docker, no cloud,
fully local (DataHub Lite is a local DuckDB-backed instance).

    python scripts/seed_datahub_lite.py            # writes outputs/acme_mcps.json
    datahub lite import --file outputs/acme_mcps.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import datahub.emitter.mce_builder as builder
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.ingestion.sink.file import write_metadata_file
from datahub.metadata.schema_classes import (
    AuditStampClass,
    ChangeAuditStampsClass,
    ChartInfoClass,
    DashboardInfoClass,
    DatasetLineageTypeClass,
    DatasetPropertiesClass,
    FineGrainedLineageClass,
    FineGrainedLineageDownstreamTypeClass,
    FineGrainedLineageUpstreamTypeClass,
    GlobalTagsClass,
    GlossaryTermAssociationClass,
    GlossaryTermsClass,
    NumberTypeClass,
    OtherSchemaClass,
    OwnerClass,
    OwnershipClass,
    OwnershipTypeClass,
    SchemaFieldClass,
    SchemaFieldDataTypeClass,
    SchemaMetadataClass,
    StringTypeClass,
    TagAssociationClass,
    UpstreamClass,
    UpstreamLineageClass,
)

_ROOT = Path(__file__).resolve().parent.parent
_NUMERIC = {"bigint", "number", "int", "integer", "float", "double", "decimal"}
_NOW = AuditStampClass(time=0, actor="urn:li:corpuser:airgap-seed")


def _field_type(native: str) -> SchemaFieldDataTypeClass:
    t = NumberTypeClass() if native.lower() in _NUMERIC else StringTypeClass()
    return SchemaFieldDataTypeClass(type=t)


def _schema_field(f: dict) -> SchemaFieldClass:
    tags = f.get("tags", [])
    terms = f.get("glossary_terms", [])
    return SchemaFieldClass(
        fieldPath=f["path"],
        type=_field_type(f.get("native_type", "")),
        nativeDataType=f.get("native_type", "string"),
        globalTags=GlobalTagsClass(
            tags=[TagAssociationClass(tag=builder.make_tag_urn(t)) for t in tags]
        )
        if tags
        else None,
        glossaryTerms=GlossaryTermsClass(
            terms=[
                GlossaryTermAssociationClass(urn=builder.make_term_urn(g)) for g in terms
            ],
            auditStamp=_NOW,
        )
        if terms
        else None,
    )


def _dataset_mcps(asset: dict, edges: list, field_edges: list) -> list:
    urn = asset["urn"]
    mcps = [
        MetadataChangeProposalWrapper(
            entityUrn=urn, aspect=DatasetPropertiesClass(name=asset["name"])
        )
    ]

    if asset.get("fields"):
        mcps.append(
            MetadataChangeProposalWrapper(
                entityUrn=urn,
                aspect=SchemaMetadataClass(
                    schemaName=asset["name"],
                    platform=builder.make_data_platform_urn(asset.get("platform", "")),
                    version=0,
                    hash="",
                    platformSchema=OtherSchemaClass(rawSchema=""),
                    fields=[_schema_field(f) for f in asset["fields"]],
                ),
            )
        )

    if asset.get("tags"):
        mcps.append(
            MetadataChangeProposalWrapper(
                entityUrn=urn,
                aspect=GlobalTagsClass(
                    tags=[TagAssociationClass(tag=builder.make_tag_urn(t)) for t in asset["tags"]]
                ),
            )
        )

    if asset.get("owners"):
        mcps.append(
            MetadataChangeProposalWrapper(
                entityUrn=urn,
                aspect=OwnershipClass(
                    owners=[
                        OwnerClass(owner=o, type=OwnershipTypeClass.DATAOWNER)
                        for o in asset["owners"]
                    ]
                ),
            )
        )

    # Lineage: dataset-level upstreams + column-level fine-grained lineage.
    upstreams = [
        UpstreamClass(dataset=e["upstream"], type=DatasetLineageTypeClass.TRANSFORMED)
        for e in edges
        if e["downstream"] == urn and e["upstream"].startswith("urn:li:dataset:")
    ]
    fine = [
        FineGrainedLineageClass(
            upstreamType=FineGrainedLineageUpstreamTypeClass.FIELD_SET,
            upstreams=[builder.make_schema_field_urn(fe["up_urn"], fe["up_field"])],
            downstreamType=FineGrainedLineageDownstreamTypeClass.FIELD,
            downstreams=[builder.make_schema_field_urn(urn, fe["down_field"])],
        )
        for fe in field_edges
        if fe["down_urn"] == urn
    ]
    if upstreams or fine:
        mcps.append(
            MetadataChangeProposalWrapper(
                entityUrn=urn,
                aspect=UpstreamLineageClass(
                    upstreams=upstreams, fineGrainedLineages=fine or None
                ),
            )
        )
    return mcps


def _consumer_mcp(asset: dict, edges: list):
    urn = asset["urn"]
    consumed = [e["upstream"] for e in edges if e["downstream"] == urn]
    stamps = ChangeAuditStampsClass(created=_NOW, lastModified=_NOW)
    if asset["entity_type"] == "dashboard":
        aspect = DashboardInfoClass(
            title=asset["name"],
            description="",
            lastModified=stamps,
            datasets=consumed,
        )
    else:  # chart
        aspect = ChartInfoClass(
            title=asset["name"],
            description="",
            lastModified=stamps,
            inputs=consumed,
        )
    return MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect)


def main() -> int:
    fixture = json.loads((_ROOT / "airgap" / "data" / "acme_datalake.json").read_text())
    edges = fixture["edges"]
    field_edges = fixture["field_edges"]

    mcps = []
    for asset in fixture["assets"]:
        if asset.get("entity_type", "dataset") == "dataset":
            mcps.extend(_dataset_mcps(asset, edges, field_edges))
        else:
            mcps.append(_consumer_mcp(asset, edges))

    out = _ROOT / "outputs"
    out.mkdir(exist_ok=True)
    target = out / "acme_mcps.json"
    write_metadata_file(target, mcps)
    print(f"wrote {len(mcps)} metadata change proposals -> {target}")
    print("next: datahub lite import --file", target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
