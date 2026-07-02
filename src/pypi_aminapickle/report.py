"""aggregate package results into human and json reports."""

import json
from dataclasses import dataclass

from pypi_aminapickle.diff import Finding

_TAGS = {
    "match": "MATCH",
    "mismatch": "MISMATCH",
    "unverified": "UNVERIFIED",
}


@dataclass(frozen=True)
class PackageResult:
    name: str
    version: str
    status: str
    reason: str
    repo_url: str | None
    ref: str | None
    findings: list[Finding]


def all_match(results: list[PackageResult]) -> bool:
    return all(result.status == "match" for result in results)


def render_text(results: list[PackageResult]) -> str:
    lines = []
    for result in results:
        tag = _TAGS.get(result.status, result.status.upper())
        pinned = f"{result.name}=={result.version}"
        if result.repo_url is not None and result.ref is not None:
            target = f" -> {result.repo_url}@{result.ref}"
        else:
            target = ""
        if result.status == "match":
            lines.append(f"[{tag}] {pinned}{target}")
        else:
            lines.append(f"[{tag}] {pinned}{target} ({result.reason})")
        for finding in result.findings:
            lines.append(f"    {finding.kind}: {finding.path}")
    lines.append(_summary(results))
    return "\n".join(lines)


def render_json(results: list[PackageResult]) -> str:
    payload = {
        "ok": all_match(results),
        "results": [
            {
                "name": result.name,
                "version": result.version,
                "status": result.status,
                "reason": result.reason,
                "repo_url": result.repo_url,
                "ref": result.ref,
                "findings": [
                    {"kind": finding.kind, "path": finding.path}
                    for finding in result.findings
                ],
            }
            for result in results
        ],
    }
    return json.dumps(payload, indent=2)


def _summary(results: list[PackageResult]) -> str:
    counts = {status: 0 for status in _TAGS}
    for result in results:
        if result.status in counts:
            counts[result.status] += 1
    return (
        f"{len(results)} packages: "
        f"{counts['match']} match, "
        f"{counts['mismatch']} mismatch, "
        f"{counts['unverified']} unverified"
    )
