"""orchestrate the per-package verification pipeline."""

from collections.abc import Callable
from contextlib import AbstractContextManager

from srcverify.attestations import AttestedSource, resolve_attested_source
from srcverify.diff import Finding, diff_trees
from srcverify.errors import SrcverifyError
from srcverify.pypi import (
    Fetcher,
    default_fetcher,
    download_sdist,
    fetch_metadata,
    select_sdist,
)
from srcverify.repo import (
    clone_repo,
    list_remote_refs,
    repo_files,
    validate_repo_url,
)
from srcverify.report import PackageResult
from srcverify.requirements import PinnedRequirement
from srcverify.sdist import extract_sdist, sdist_files
from srcverify.source import candidate_refs, resolve_repo_url, select_ref
from srcverify.workspace import workspace

_RefLister = Callable[[str], list[str]]
_Cloner = Callable[[str, str, str], str]
_WorkspaceFactory = Callable[[], AbstractContextManager[str]]
_AttestationResolver = Callable[
    [str, str, str, str, Fetcher], AttestedSource | None
]


def verify_package(
    req: PinnedRequirement,
    *,
    fetch: Fetcher = default_fetcher,
    list_refs: _RefLister = list_remote_refs,
    clone: _Cloner = clone_repo,
    resolve_attested: _AttestationResolver = resolve_attested_source,
    make_workspace: _WorkspaceFactory = workspace,
) -> PackageResult:
    repo_url: str | None = None
    ref: str | None = None
    with make_workspace() as work:
        try:
            metadata = fetch_metadata(req.name, req.version, fetch)
            sdist = download_sdist(select_sdist(metadata), work, fetch)
            sdist_tree = sdist_files(extract_sdist(sdist.path, work))
            attested = resolve_attested(
                req.name,
                req.version,
                sdist.ref.filename,
                sdist.ref.sha256,
                fetch,
            )
            if attested is not None:
                repo_url = attested.repo_url
                ref = attested.commit
            else:
                repo_url = validate_repo_url(resolve_repo_url(metadata))
                ref = select_ref(
                    candidate_refs(req.name, req.version),
                    list_refs(repo_url),
                )
            repo_tree = repo_files(clone(repo_url, ref, work))
        except SrcverifyError as exc:
            return _result(req, "unverified", str(exc), repo_url, ref, [])
    findings = diff_trees(sdist_tree, repo_tree)
    if findings:
        noun = "file" if len(findings) == 1 else "files"
        reason = f"{len(findings)} differing {noun}"
        return _result(req, "mismatch", reason, repo_url, ref, findings)
    return _result(req, "match", "matches source", repo_url, ref, [])


def _result(
    req: PinnedRequirement,
    status: str,
    reason: str,
    repo_url: str | None,
    ref: str | None,
    findings: list[Finding],
) -> PackageResult:
    return PackageResult(
        name=req.name,
        version=req.version,
        status=status,
        reason=reason,
        repo_url=repo_url,
        ref=ref,
        findings=findings,
    )
