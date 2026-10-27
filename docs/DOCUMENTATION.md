# Airgap Technical Documentation

> Local-first data governance & PII lineage auditor for DataHub.
> Built for the DataHub Agent Hackathon (Wildcard / Regulatory Automation).

This document explains **what Airgap is, the problem it solves, how it works
end to end, and exactly how DataHub is integrated.**

---

## 1. What Airgap is

Airgap is a command-line agent that audits a data catalog for **PII governance
leaks**: places where sensitive data has flowed downstream through lineage but
lost its classification, or ended up in an asset that nobody owns. It reads its
context from **DataHub** (schemas, tags, glossary terms, ownership, and
lineage), applies deterministic detection rules, and uses a **local LLM
(Ollama)** to turn each finding into a plain-language, compliance-oriented
explanation.

Its defining property: **nothing leaves your machine.** The detection is local
code and the language model is local. The only network calls Airgap makes are
read-only queries to the DataHub instance you explicitly point it at.

> The one-liner: *an air-gapped auditor for the data you can't afford to leak.*

---

## 2. The problem it solves

In a modern data stack, PII is usually classified correctly **at the source**
(e.g. `users.email` is tagged `PII` / `Email` / `Classification.Sensitive`).
The problem is what happens next:

1. That column is copied, joined, and transformed through staging tables, marts,
   marketing tables, and ML feature stores.
2. **Classification does not automatically travel with the data.** A downstream
   `marketing_enriched.email` column often carries no PII tag at all.
3. Those derived assets frequently have **no owner**, so when a regulator or an
   incident asks "who is responsible for this PII?", there's no answer.
4. Auditing this by hand means walking the lineage graph node by node, which
   does not scale.
5. The obvious fix, pointing an LLM agent at your catalog, usually means shipping
   your schemas and lineage to a **cloud model**. For a tool whose entire job is
   protecting sensitive data, that is self-defeating.

**Airgap closes exactly this gap:** automated, lineage-aware PII leak detection
that runs entirely locally.

---

## 3. What it does (features)

- **Reads DataHub metadata**: datasets, schema fields, field-level tags &
  glossary terms, dataset-level tags, ownership, and dataset- and column-level
  lineage.
- **Detects governance leaks** with two deterministic lineage rules (R1 and R2)
  and an opt-in name-based rule (R3, see §6).
- **Scores severity by blast radius**, meaning how many downstream consumers
  a leak reaches, escalating to CRITICAL when PII reaches human-facing BI
  (dashboards, charts).
- **Explains findings locally** via Ollama, in GDPR-framed, plain-language prose,
  never deciding the finding, only describing it.
- **Produces four artifacts** per run by default:
  - `findings.json`: machine-readable findings, versioned (see §9.1)
  - `report.md`: human-readable governance report
  - `lineage_graph.html`: an offline, self-contained lineage leak map
  - `outputs/patches/*.py`: ready-to-run DataHub SDK remediation code

  `--format` selects the report files, and `--format sarif` adds
  `findings.sarif`, a SARIF 2.1.0 log (see §9.2).
- **Source-agnostic**: the exact same detection runs against a live DataHub
  instance or the bundled synthetic fixture.
- **CI-friendly**: `--fail-on {critical,high,medium}` returns exit code 2
  when any finding is at or above that severity (`--fail-on-critical` is the
  same as `--fail-on critical`).

---

## 4. How it works, end to end

```
┌─ source ─────────────┐
│ DataHub (GraphQL)    │  read-only, HTTPS
│   or                 │
│ bundled fixture JSON │
└──────────┬───────────┘
           │  normalize
           ▼
┌─ MetadataGraph ──────┐   the source-agnostic contract:
│ assets, edges,       │   assets{urn→Asset}, lineage edges,
│ field_edges          │   column-level field edges
└──────────┬───────────┘
           │  run_rules()  (deterministic)
           ▼
┌─ Findings ───────────┐   R1 untagged PII propagation
│ severity, evidence,  │   R2 ownerless sensitive asset
│ blast radius,        │   + blast-radius severity
│ remediation          │
└──────────┬───────────┘
           │  enrich(): local Ollama, localhost:11434 only
           ▼
┌─ Outputs ────────────┐
│ findings.json        │
│ report.md            │
│ lineage_graph.html   │
│ patches/*.py         │
└──────────────────────┘
```

Step by step:

1. **Fetch.** A `MetadataSource` (`FixtureSource` or `DataHubSource`) returns a
   fully normalized `MetadataGraph`. Both sources produce the identical shape,
   so nothing downstream knows or cares where the metadata came from.
2. **Detect.** `run_rules()` applies R1, R2 and (when configured) R3 over the
   graph, computing
   evidence (the column-level lineage path for R1, a one-line reason for R2)
   and a blast-radius severity for each finding. This is
   plain, unit-tested Python, and **no LLM is involved in deciding a finding.**
3. **Explain.** If Ollama is reachable, each finding is sent to a local model
   which returns an explanation of two or three sentences and an urgency
   assessment. If Ollama is not running, Airgap still emits the complete
   deterministic report.
4. **Emit.** Airgap writes the four artifacts and prints a colored console
   summary.

**Why the split matters:** deterministic detection makes results reproducible
and hallucination-free; the LLM is confined to the "communication" layer where
mistakes are low-risk and easy to review.

---

## 5. How DataHub is integrated

DataHub is Airgap's **context platform**, the source of truth for schema,
classification, ownership, and lineage. Integration happens in
`airgap/sources/datahub.py` (`DataHubSource`) through DataHub's **GraphQL API**,
using only read-only queries.

### 5.1 Discovering datasets
Airgap paginates `search(input: {type: DATASET, query: "*"})` to enumerate every
dataset URN in the catalog.

### 5.2 Reading each dataset
For each URN it queries the `dataset(urn:)` resolver for:
- `platform { name }`
- dataset-level `tags`
- `ownership { owners }`
- `schemaMetadata { fields { fieldPath nativeDataType globalTags glossaryTerms } }`
  (this is where **field-level PII classification** lives)
- `fineGrainedLineages`: DataHub's **column-level lineage**, used for precise
  field-to-field leak tracing

### 5.3 Reading lineage
Starting from every dataset, it queries the
`entity(urn:).lineage(input:{direction: DOWNSTREAM})` resolver one hop at a
time, 200 results per page, to build the asset-level lineage edges.
Dashboards, charts, data jobs, data flows and ML models that it reaches are
added as assets with their entity type, name, platform and owners, so
human-facing consumers can raise severity. Their own downstream lineage is
followed too, up to `datahub.lineage_depth` hops from the dataset (default 4).

### 5.4 Normalization
GraphQL responses are mapped into the `MetadataGraph` model
(`airgap/model.py`): `Asset`, `Field`, `LineageEdge`, `FieldLineage`. In the
GraphQL `fineGrainedLineages` response each upstream and downstream is a
`SchemaFieldRef { urn path }`, where `urn` is the dataset URN and `path` is the
field path, so they become `FieldLineage` values directly. Full `schemaField`
URNs (`urn:li:schemaField:(<datasetUrn>,<fieldPath>)`), which is what DataHub
Lite returns, are split back into `(dataset_urn, field_path)` so column-level
lineage lines up with the schema.

### 5.5 Writing back (remediation)
Airgap never mutates DataHub directly. Instead it **generates** DataHub Python
SDK code (`acryl-datahub`) that a data engineer reviews and runs to fix each
finding. The code emits `GlobalTagsClass` / `GlossaryTermsClass` on the leaked
fields (R1) or `OwnershipClass` on the ownerless asset (R2). These artifacts are
designed to drop straight into a pull request.

### 5.6 Three sources, one model
Airgap has three interchangeable metadata sources, all normalizing into the same
`MetadataGraph`:

1. **`datahub-lite`: a real, local, Docker-free DataHub.** This is the primary
   integration for reproducibility. `scripts/setup_datahub_lite.sh` installs
   [DataHub Lite](https://docs.datahub.com/docs/datahub-lite) (a DuckDB-backed
   DataHub), converts the Acme fixture into genuine DataHub metadata aspects via
   the official SDK (`scripts/seed_datahub_lite.py` with `SchemaMetadata`,
   `GlobalTags`, `GlossaryTerms`, `Ownership`, `UpstreamLineage` with
   `FineGrainedLineage`, `DashboardInfo`/`ChartInfo`), and imports them.
   `DataHubLiteSource` then reads them back through the public `datahub lite`
   CLI, with one `datahub lite export` call (falling back to one
   `datahub lite get` per entity if the export command fails). This
   proves Airgap runs against real DataHub metadata with **no Docker and no
   cloud**, which is the whole point of a local-first tool.
2. **`datahub`: live GMS** via GraphQL (§5.1 to §5.4), for any hosted instance.
3. **`fixture`: synthetic**, zero-setup, using the *same URN format and schema
   model* as real DataHub. Useful for a dependency-free demo and as the seed for
   DataHub Lite.

Because all three produce an identical `MetadataGraph`, the detection engine is
exercised the same way regardless of source: the synthetic fixture and the real
DataHub Lite instance yield the **same five findings**.

---

## 6. Detection rules

### R1: Untagged PII propagation
A field classified as PII/sensitive flows, through column-level lineage, into a
downstream field/dataset that carries **no equivalent classification.**

Algorithm:
1. Find **true PII origins**: sensitive fields with no sensitive upstream field
   (where PII first enters the graph).
2. BFS the column-level lineage from each origin.
3. Any reached downstream field that is **not** itself classified **and** whose
   dataset carries no PII tag is a leak.
4. Group leaks by offending dataset; attach the full origin→leak lineage path as
   evidence.

Example evidence:
`acme.public.users.email → acme.staging.stg_users.email → acme.analytics.dim_customer.email → acme.marketing.marketing_enriched.email`

### R2: Ownerless sensitive asset
A dataset that holds sensitive data (directly, or by receiving it through
lineage from a classified source) has **no owner**, so nobody is accountable.

### R3: Likely-unclassified PII by column name (opt-in)
A field whose **name** looks like personal data but carries no marker: a name
candidate, not a finding about data. Off unless `detection.name_patterns` is
configured; when on, every dot-separated segment of `Field.path` is compared
against each label's regex with `re.fullmatch` (case-insensitive), so
`profiles.email` matches `email` while a counter such as
`email_opt_in_count` does not. Findings are reported at **LOW** severity and
never become lineage origins, so a name guess cannot make R1 or R2 fire.

```yaml
detection:
  name_patterns:
    email: "e?mail(_?address)?"
    phone: "(phone|mobile|gsm)(_?number)?"
    national_id: "(tckn|ssn|national_?id)"
    iban: "iban"
    ip_address: "(ip|ip_?address)"
    date_of_birth: "(date_?of_?birth|dob|birth_?date)"
```

Keep the patterns anchored by writing them for a whole segment;
`re.fullmatch` already rejects a partial name.

### Severity (blast radius)
Severity is driven by the transitive downstream consumers of the offending
asset:
- **CRITICAL**: reaches a human-facing consumer (dashboard/chart), i.e. PII is
  visible to real users, or blast radius ≥ configured threshold.
- **HIGH**: has downstream consumers, but none human-facing.
- **MEDIUM**: internal only, no downstream consumers yet.
- **LOW**: R3 name candidates; they never feed R1 or R2.

All thresholds and the PII marker vocabulary are configurable in `config.yaml`.

---

## 7. The local LLM layer

`airgap/llm/ollama.py` calls Ollama's `/api/generate` on `localhost:11434`. For
each finding it sends the structured facts (rule, asset, leaked fields, lineage
evidence, blast radius) and asks for a short DPO-facing explanation of the risk
and urgency. Key guarantees:
- The prompt forbids inventing facts beyond what's given.
- A failure or an unreachable Ollama never breaks the audit; the report is
  still produced deterministically.
- No metadata is ever sent anywhere but localhost.

Model is configurable (`qwen2.5:7b` by default; any Ollama model works).

---

## 8. Repository layout

```
airgap/
├── model.py            normalized metadata model (source-agnostic contract)
├── cli.py              CLI: `airgap audit`
├── sources/
│   ├── base.py         MetadataSource interface
│   ├── datahub.py      live DataHub GraphQL source
│   ├── datahub_lite.py local DataHub Lite source (via `datahub lite` CLI)
│   └── fixture.py      synthetic-fixture source
├── detect/
│   ├── findings.py     Finding model, marker matching, severity scoring
│   └── rules.py        R1 + R2 + opt-in R3 detection
├── llm/ollama.py       local explanation layer
├── report/
│   ├── findings_json.py  findings.json (versioned)
│   ├── markdown.py     report.md
│   ├── graph_html.py   offline lineage leak map
│   └── sarif.py        findings.sarif (SARIF 2.1.0)
├── remediate/patches.py  DataHub SDK remediation code generator
└── data/
    ├── config.yaml     bundled default config (copy of the root config.yaml)
    └── acme_datalake.json  synthetic DataHub-shape catalog with planted leaks

examples/                     sample outputs (findings, report, graph, patches)
tests/                        detection and CLI-defaults tests
config.yaml                   markers, thresholds, source & Ollama config
scripts/                      DataHub Lite setup + seeding scripts
docs/                         this document, PRD, writeup, demo film, deck, media
```

---

## 9. Usage

```bash
# Bundled fixture (default, offline)
airgap audit

# Deterministic only (skip the LLM)
airgap audit --no-llm

# Live DataHub
airgap audit --source datahub --url https://your.acryl.io --token $TOKEN

# CI gate: exit 2 on any HIGH or CRITICAL finding
airgap audit --fail-on high

# Only JSON and SARIF, for a code-scanning tool
airgap audit --no-llm --format json --format sarif
```

Config lookup: `--config PATH` if given, else `./config.yaml` in the current
directory, else the default config bundled in `airgap/data/`. Outputs are
written to `./outputs/` in the current directory unless `--out DIR` is given.

### 9.1 `findings.json` schema

```json
{
  "schema_version": 1,
  "airgap_version": "0.2.0",
  "generated_at": "2026-10-25T12:00:00Z",
  "source": "fixture",
  "findings": [ ... ]
}
```

| Key | Type | Meaning |
|---|---|---|
| `schema_version` | integer | Version of this layout. It goes up when a key is removed, renamed or changes meaning. New keys can be added without a bump, so readers should ignore keys they do not know. |
| `airgap_version` | string | `airgap.__version__` of the run. |
| `generated_at` | string | UTC time of the run, ISO 8601 with a `Z` suffix, to the second. |
| `source` | string | `fixture`, `datahub-lite` or `datahub`. |
| `findings` | array | One object per finding, sorted by severity, then by blast radius (largest first), then by ID. |

Each finding has these keys:

| Key | Type | Meaning |
|---|---|---|
| `id` | string | For example `AIRGAP-R1-001`. Numbered per run, so the same leak can get a different ID in another run. |
| `rule` | string | `R1` or `R2` (see §6). |
| `title` | string | One-line summary. |
| `severity` | string | `CRITICAL`, `HIGH` or `MEDIUM` (see §6, Severity). |
| `asset_urn`, `asset_name` | string | The dataset the finding is about. |
| `leaked_fields` | array of strings | R1: the downstream fields without a sensitive marker. Empty for R2. |
| `evidence` | array of strings | R1: one lineage path per leaked field. R2: a one-line reason. |
| `blast_radius` | integer | Number of downstream consumers of the asset. |
| `consumers` | object | Downstream consumer count per entity type, for example `{"chart": 1}`. |
| `remediation` | string | Suggested fix. |
| `explanation` | string | Prose from the local LLM; empty with `--no-llm` or when Ollama is not reachable. |

`tests/test_output_formats.py` pins these keys.

### 9.2 SARIF output

`--format sarif` writes `findings.sarif`, a SARIF 2.1.0 log with one run.
The test suite validates it against the official
[SARIF 2.1.0 JSON schema](https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json),
a copy of which is in `tests/data/`.

| SARIF | Comes from |
|---|---|
| `tool.driver.name`, `version` | `airgap`, `airgap.__version__` |
| `tool.driver.rules` | R1 (`UntaggedPiiPropagation`) and R2 (`OwnerlessSensitiveAsset`) |
| `result.ruleId`, `ruleIndex` | the finding's `rule` |
| `result.level` | CRITICAL and HIGH map to `error`, MEDIUM to `warning` (and LOW to `note`). SARIF has no level above `error`. |
| `result.message.text` | the title, plus the leaked fields |
| `result.locations[0].logicalLocations[0]` | `name` is the asset name, `fullyQualifiedName` the asset URN |
| `result.partialFingerprints["airgapFinding/v1"]` | SHA-256 of rule, asset URN and sorted leaked fields, so the same leak keeps the same fingerprint across runs (finding IDs do not) |
| `result.properties` | `id`, `severity`, `blast_radius`, `consumers`, `leaked_fields`, `evidence`, `remediation`, and `explanation` when present |
| `invocations[0].endTimeUtc` | the same time as `generated_at` in `findings.json` |
| `run.properties.source` | the metadata source |

A finding points at a catalog asset, not at a file, so results have a logical
location and no physical location (file and line). Tools that need a file
location for every result may not display them.

---

## 10. Limitations & roadmap

- **Now:** R1 (untagged PII propagation) and R2 (ownerless sensitive asset),
  dataset- and column-level lineage, blast-radius severity, local explanations,
  remediation code generation.
- **Stretch (designed, not yet enabled):** R3 broken-classification-chain, R4
  policy/retention gaps, and reading directly through the **DataHub MCP Server**
  in addition to GraphQL.
- R1 depends on column-level lineage. It walks only `fineGrainedLineages`
  (the graph's `field_edges`) and never falls back to dataset-level lineage,
  so a flow that has no column-level edges produces no R1 finding.
  Dataset-level edges are used only to compute blast radius and severity.
  R2 still flags an ownerless dataset that carries a sensitive marker
  directly, but it can only see PII that arrives through lineage when
  column-level edges exist.
