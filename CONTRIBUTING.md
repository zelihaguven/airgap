# Contributing to Airgap

Thanks for helping. Airgap is a small project, so the process is light. This
guide covers the dev setup, running the tests, and what a good pull request
looks like.

## Ground rules

- **Detection stays deterministic.** Rules in `airgap/detect/` are plain,
  testable code. The local LLM layer (`airgap/llm/`) only explains findings.
  It must never decide them.
- **Local-first.** Do not add calls to cloud services. The only network
  traffic Airgap makes is read-only queries to the DataHub instance the user
  points it at, plus Ollama on localhost.
- **No real data in the repo.** Fixtures, examples and test data must be
  synthetic. Never commit real catalog metadata, tokens or credentials.
- **Be respectful.** Everyone taking part follows the
  [Code of Conduct](CODE_OF_CONDUCT.md). Report security problems as described
  in [SECURITY.md](SECURITY.md), not in a public issue.

## Dev setup

Python 3.10 or newer is required.

```bash
git clone https://github.com/zelihaguven/airgap.git
cd airgap
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
```

Optional extras:

- `pip install -e ".[datahub-lite]"` installs DataHub Lite for the
  `--source datahub-lite` path. `bash scripts/setup_datahub_lite.sh` does the
  whole setup and seeding in one step.
- [Ollama](https://ollama.com) with `ollama pull qwen2.5:7b` enables the
  prose explanations. Use `--no-llm` to skip them.

## Running the tests

```bash
./.venv/bin/python -m pytest -v
```

CI runs the same command on Python 3.10, 3.11 and 3.12, followed by a smoke
run of the CLI:

```bash
./.venv/bin/airgap audit --no-llm --out /tmp/airgap-out
```

The tests in `tests/test_detection.py` pin the expected findings for the Acme
fixture. If you change a rule or the fixture on purpose, update the
assertions in the same PR and explain why in the description.

To check the package build:

```bash
./.venv/bin/pip install build twine
./.venv/bin/python -m build
./.venv/bin/twine check dist/*
```

## Pull requests

- Open an issue first for anything larger than a small fix, so we can agree
  on the approach.
- Keep each PR focused on one change. Branch from `main`.
- Use [Conventional Commits](https://www.conventionalcommits.org/) for commit
  messages and PR titles, for example `feat(detect): add R3 for ...`,
  `fix(sources): ...`, `docs: ...`, `ci: ...`, `test: ...`.
- Add or update tests for every behavior change. New rules need a fixture
  case that triggers them and one that must not.
- Add a line under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md) for
  user-visible changes.
- Make sure `pytest` passes locally before you ask for review.
- Fill in the pull request template.

## Reporting bugs and requesting features

Use the issue templates. For bugs, include the command you ran, the source
(`fixture`, `datahub-lite` or `datahub`), your Python and Airgap versions,
and the full error output, with any real URNs, hostnames or tokens redacted.

## License

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE).
