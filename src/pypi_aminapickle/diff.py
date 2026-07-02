"""compare the sdist tree against the source repo tree."""

from dataclasses import dataclass

from pypi_aminapickle.digests import EMPTY_SETUP_CFG_DIGEST


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str


def diff_trees(sdist: dict[str, str], repo: dict[str, str]) -> list[Finding]:
    findings = []
    for path, digest in sdist.items():
        if _is_generated(path):
            continue
        if path not in repo:
            if _is_generated_setup_cfg(path, digest):
                continue
            findings.append(Finding(kind="extra", path=path))
        elif repo[path] != digest:
            findings.append(Finding(kind="altered", path=path))
    findings.sort(key=lambda finding: (finding.path, finding.kind))
    return findings


def _is_generated(path: str) -> bool:
    if path == "PKG-INFO":
        return True
    return any(part.endswith(".egg-info") for part in path.split("/"))


def _is_generated_setup_cfg(path: str, digest: str) -> bool:
    return (
        path.split("/")[-1] == "setup.cfg" and digest == EMPTY_SETUP_CFG_DIGEST
    )
