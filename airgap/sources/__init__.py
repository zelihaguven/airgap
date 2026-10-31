from airgap.sources.base import MetadataSource
from airgap.sources.datahub import DataHubSource
from airgap.sources.datahub_lite import DataHubLiteSource
from airgap.sources.fixture import FixtureSource

__all__ = [
    "MetadataSource",
    "FixtureSource",
    "DataHubSource",
    "DataHubLiteSource",
    "build_source",
]


def build_source(cfg: dict) -> MetadataSource:
    """Construct the metadata source selected in config."""
    kind = cfg.get("source", "fixture")
    if kind == "fixture":
        return FixtureSource(cfg.get("fixture_path") or None)
    if kind == "datahub-lite":
        return DataHubLiteSource(datahub_bin=cfg.get("datahub_lite", {}).get("bin"))
    if kind == "datahub":
        dh = cfg.get("datahub", {})
        return DataHubSource(
            url=dh.get("url", ""),
            token=dh.get("token", ""),
            lineage_depth=int(dh.get("lineage_depth", 4)),
        )
    raise ValueError(
        f"Unknown source: {kind!r} (expected 'fixture', 'datahub-lite', or 'datahub')"
    )
