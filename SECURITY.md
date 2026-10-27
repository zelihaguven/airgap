# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 0.2.x | Yes |
| 0.1.x | No |

## Reporting a vulnerability

Please do not report security problems in a public issue, pull request or
discussion.

Report them privately through GitHub private vulnerability reporting:
open the [Security tab](https://github.com/zelihaguven/airgap/security) and
choose **Report a vulnerability**, or go straight to
[the reporting form](https://github.com/zelihaguven/airgap/security/advisories/new).
Only you and the repository maintainers can see the report. The maintainer
is [@zelihaguven](https://github.com/zelihaguven).

Include what you can of:

- the Airgap version (`airgap --version`) and Python version;
- the source you used (`fixture`, `datahub-lite` or `datahub`);
- the steps or config needed to reproduce the problem, and what an attacker
  gains from it.

Redact real URNs, hostnames, tokens and catalog metadata before you attach
anything.

## Scope

Airgap reads metadata and writes local report files. It never writes to
DataHub. Examples of what to report:

- network traffic other than the read-only queries to the configured DataHub
  and the configured Ollama endpoint;
- a token or other secret written to a report, a log or the terminal;
- a crafted catalog, config or DataHub response that makes Airgap run code or
  write outside the output directory.

The remediation scripts in `patches/` are meant to be reviewed and run by you.
What they do once you run them is not a vulnerability in Airgap, unless the
generated code differs from what the finding describes.
