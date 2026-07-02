"""clone a source repo at a ref and hash its tracked files."""

import os
import shutil
import subprocess
from pathlib import PurePath
from urllib.parse import urlparse

from pypi_aminapickle.digests import file_digest
from pypi_aminapickle.errors import CloneError, InvalidRepoUrl, RefNotFound

_TIMEOUT = 300.0

_HARDENING = [
    "-c",
    "protocol.ext.allow=never",
    "-c",
    "protocol.file.allow=user",
    "-c",
    f"core.hooksPath={os.devnull}",
]


def validate_repo_url(url: str) -> str:
    if url.startswith("-"):
        raise InvalidRepoUrl(f"option-like url: {url!r}")
    if "::" in url:
        raise InvalidRepoUrl(f"transport helper url: {url!r}")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise InvalidRepoUrl(f"non-https url: {url!r}")
    if not parsed.netloc:
        raise InvalidRepoUrl(f"url has no host: {url!r}")
    return url


def clone_repo(url: str, ref: str, dest_dir: str) -> str:
    if url.startswith("-"):
        raise InvalidRepoUrl(f"option-like url: {url!r}")
    if ref.startswith("-"):
        raise RefNotFound(f"option-like ref: {ref!r}")
    checkout = os.path.join(dest_dir, "repo")
    if _shallow_fetch(url, ref, checkout):
        return checkout
    return _full_clone(url, ref, checkout)


def _shallow_fetch(url: str, ref: str, checkout: str) -> bool:
    init = _run_git(["init", "--quiet", checkout])
    if init.returncode != 0:
        shutil.rmtree(checkout, ignore_errors=True)
        return False
    fetch = _run_git(
        ["-C", checkout, "fetch", "--depth", "1", "--quiet", "--", url, ref]
    )
    if fetch.returncode == 0:
        detach = _run_git(
            ["-C", checkout, "checkout", "--quiet", "--detach", "FETCH_HEAD"]
        )
        if detach.returncode == 0:
            return True
    shutil.rmtree(checkout, ignore_errors=True)
    return False


def _full_clone(url: str, ref: str, checkout: str) -> str:
    clone = _run_git(["clone", "--quiet", "--no-checkout", "--", url, checkout])
    if clone.returncode != 0:
        raise CloneError(f"git clone failed: {clone.stderr.strip()}")
    result = _run_git(
        ["-C", checkout, "checkout", "--quiet", "--detach", ref, "--"]
    )
    if result.returncode != 0:
        raise RefNotFound(f"ref {ref!r} not found: {result.stderr.strip()}")
    return checkout


def list_remote_refs(url: str) -> list[str]:
    if url.startswith("-"):
        raise InvalidRepoUrl(f"option-like url: {url!r}")
    result = _run_git(["ls-remote", "--tags", "--heads", "--", url])
    if result.returncode != 0:
        raise CloneError(f"git ls-remote failed: {result.stderr.strip()}")
    refs = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 2 or parts[1].endswith("^{}"):
            continue
        for prefix in ("refs/tags/", "refs/heads/"):
            if parts[1].startswith(prefix):
                refs.append(parts[1][len(prefix) :])
                break
    return refs


def repo_files(checkout_dir: str) -> dict[str, str]:
    tree: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(checkout_dir):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for filename in filenames:
            full = os.path.join(dirpath, filename)
            if os.path.islink(full):
                continue
            key = PurePath(os.path.relpath(full, checkout_dir)).as_posix()
            tree[key] = file_digest(key, full)
    return tree


def _run_git(
    args: list[str], cwd: str | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *_HARDENING, *args],
            cwd=cwd,
            env=_git_env(),
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise CloneError(f"git failed to run: {exc}") from exc


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    return env
