"""Local explanation layer backed by Ollama.

CRITICAL DESIGN POINT: the LLM never *decides* anything. Detection is done by
deterministic rules; the model only turns a structured finding into readable
prose and remediation guidance. Every call goes to localhost — no metadata
leaves the machine. This is what makes Airgap safe to run on real catalogs.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from airgap.detect.findings import Finding

_PROMPT = """You are a data-governance analyst. Explain the following finding to a \
data protection officer in 2-3 short sentences: what is wrong, why it is a \
compliance/privacy risk (e.g. GDPR), and how urgent it is. Be concrete and \
plain. Do not invent facts beyond what is given.

Finding:
- Rule: {rule} ({title})
- Severity: {severity}
- Affected asset: {asset_name}
- Leaked fields: {fields}
- Lineage evidence: {evidence}
- Blast radius (downstream consumers): {blast} {consumers}

Explanation:"""


class LocalLLM:
    def __init__(
        self,
        url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        timeout: int = 120,
    ) -> None:
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def available(self) -> bool:
        try:
            req = urllib.request.Request(self.url + "/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _generate(self, prompt: str) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.url + "/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return (data.get("response") or "").strip()

    def enrich(self, finding: Finding) -> str:
        prompt = _PROMPT.format(
            rule=finding.rule,
            title=finding.title,
            severity=finding.severity,
            asset_name=finding.asset_name,
            fields=", ".join(finding.leaked_fields) or "(asset-level)",
            evidence=" | ".join(finding.evidence),
            blast=finding.blast_radius,
            consumers=finding.consumers,
        )
        try:
            return self._generate(prompt)
        except Exception:  # never let the LLM break the audit
            # An empty explanation means "no prose"; the caller reports the
            # failure once instead of storing a raw exception in the report.
            return ""
