# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Opt-in rule R3 reports columns whose name looks like personal data, set
  with `detection.name_patterns` (a map of label to regex). Off by default.
  Matches are LOW severity, grouped per dataset, and never feed R1 or R2
  (#47, fixes #7).
- Unit tests for the GMS and DataHub Lite source parser helpers, with
  synthetic payloads and no network (#46, fixes #8).

### Contributors

Thanks to @bfs2021 (#46, #47).

## [0.2.0] - 2026-10-25

Bug fixes from the v0.1.0 QA campaign, a faster DataHub Lite read, readable
CLI errors, a versioned `findings.json` and SARIF output.

### Added

- `airgap --version` prints the installed version (#40).
- `AIRGAP_DATAHUB_TOKEN` for the GMS token. Precedence is `--token`, then
  `AIRGAP_DATAHUB_TOKEN`, then `datahub.token` (#40).
- `findings.json` now starts with `schema_version` (1), `airgap_version`
  and `generated_at`. The layout is documented in `docs/DOCUMENTATION.md`
  (#43, fixes #6).
- `--format {json,md,html,sarif}` (repeatable) selects the report files.
  The default is still `json`, `md` and `html`. `sarif` writes
  `findings.sarif`, a SARIF 2.1.0 log (#43, fixes #6).
- `--fail-on {critical,high,medium}` exits with 2 when any finding is at or
  above that severity. `--fail-on-critical` still works and means
  `--fail-on critical` (#43, fixes #6).
- GMS source: dashboards, charts and other lineage consumers are loaded as
  assets, so they can escalate a finding to CRITICAL. `datahub.lineage_depth`
  is now honored and lineage results are paged (#30, fixes #4).
- Scenario tests from the v0.1.0 QA campaign (#14, #17).

### Fixed

- GMS source: tags and glossary terms without `properties.name` are matched
  as PII markers (#9, fixes #3).
- GMS source: column-level lineage is read from `SchemaFieldRef` `urn` and
  `path`, so R1 fires against GMS (#16, fixes #2).
- The `datahub-lite` extra installs DuckDB again with acryl-datahub
  1.7.0.14 and later (#31, fixes #18).
- Leaks downstream of a classified lineage cycle are found (#32, fixes #19).
- A config without a `detection:` block uses the bundled defaults, and an
  empty `pii_markers` is a config error (#34, fixes #20).
- Turkish dotted and dotless i match in markers, for example `KİŞİSEL` and
  `Kişisel` (#35, fixes #21).
- Fixture entries that share a URN are merged instead of overwritten
  (#36, fixes #22).
- The lineage graph renders for an empty catalog (#37, fixes #23), and graph
  layers are computed without recursion, so long chains no longer crash
  (#38, fixes #24).
- Blast radius no longer counts the asset itself inside a lineage cycle
  (#39, fixes #27).
- Remediation patches from an earlier run are removed when `--out` is reused
  (#41, fixes #25).
- Ollama errors are no longer written into the report as explanations
  (#44, fixes #29).
- User mistakes and unreachable services print one `airgap: error:` line
  and exit with 1 instead of a Python traceback (#40).
- The sdist ships `config.yaml` and the tests, so pytest passes from an
  unpacked sdist (#12).

### Changed

- `ollama.prose_model` is removed from the sample configs. No code read it,
  and a config that still sets it keeps working (#40).
- Docs: README refresh, R1 has no dataset-level fallback, and a "What may
  change" note (#10, #11, #13, #15).

### Performance

- Lineage edges are indexed, so detection is no longer quadratic
  (#33, fixes #5).
- The `datahub-lite` source reads the catalog with one `datahub lite export`
  and falls back to per-entity reads if the export fails (#42, fixes #26).

### Contributors

Thanks to @evandroribeiro94 (#9) and @bfs2021 (#41, #44) for their first
contributions.

## [0.1.0] - 2026-10-25

First public release, published on PyPI as `airgap-datahub`. The command and
the import name are `airgap`.

### Added

- `airgap audit` CLI with `--config`, `--source`, `--url`, `--token`,
  `--model`, `--no-llm`, `--out` and `--fail-on-critical` (exit code 2 when
  any CRITICAL finding exists, for CI use).
- Works out of the box after `pip install`: the default config and the demo
  catalog ship as package data. Config lookup is `--config PATH`, then
  `./config.yaml` in the current directory, then the bundled default.
  Outputs go to `./outputs/` in the current directory by default (`--out`
  to change it).
- Three metadata sources that normalize into one `MetadataGraph` model:
  - `fixture`: the bundled synthetic Acme catalog
    (`airgap/data/acme_datalake.json`), fully offline.
  - `datahub-lite`: a local, Docker-free DataHub Lite instance, read through
    the `datahub lite` CLI (`schemaMetadata`, `ownership`, `upstreamLineage`
    with `fineGrainedLineages`, `dashboardInfo`/`chartInfo`).
  - `datahub`: a live DataHub GMS over read-only GraphQL, with optional
    bearer token.
- Deterministic detection rules:
  - **R1, untagged PII propagation**: a field classified as sensitive flows
    through column-level lineage into a downstream field or dataset with no
    equivalent classification.
  - **R2, ownerless sensitive asset**: a dataset that holds sensitive data,
    directly or through lineage, has no owner.
- Severity scoring by blast radius (transitive downstream consumers).
  Human-facing consumers (dashboards, charts) escalate a finding to CRITICAL.
  Thresholds and the PII marker vocabulary are configurable in `config.yaml`.
- Evidence on every finding: R1 findings carry the column-level lineage path
  from the PII origin to each leaked field, and R2 findings carry a one-line
  reason.
- Optional explanations from a local Ollama model (localhost only). The LLM
  never decides findings, and the audit still completes if Ollama is
  unreachable.
- Outputs: `findings.json`, `report.md`, a self-contained offline
  `lineage_graph.html` leak map, and one reviewable DataHub SDK remediation
  script per finding in `patches/`. Airgap never writes to DataHub itself.
- `scripts/setup_datahub_lite.sh` and `scripts/seed_datahub_lite.py` to stand
  up and seed a local DataHub Lite with the Acme catalog.
- Detection regression tests against the Acme fixture, and tests for the
  CLI's config and output-directory defaults (`tests/`).
- Sample outputs in `examples/`, plus documentation, PRD, demo film, slide
  deck and media in `docs/`.
- GitHub Actions: tests on Python 3.10, 3.11 and 3.12, and PyPI Trusted
  Publishing on release.

[Unreleased]: https://github.com/zelihaguven/airgap/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/zelihaguven/airgap/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/zelihaguven/airgap/releases/tag/v0.1.0
