"""clone a source repo at a ref and hash its tracked files."""

import hashlib
import os
import subprocess
from pathlib import PurePath
from urllib.parse import urlparse

from srcverify.errors import CloneError, InvalidRepoUrl, RefNotFound

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
    clone = _run_git(
        ["clone", "--quiet", "--no-checkout", "--", url, checkout],
        cwd=dest_dir,
    )
    if clone.returncode != 0:
        raise CloneError(f"git clone failed: {clone.stderr.strip()}")
    result = _run_git(
        ["checkout", "--quiet", "--detach", ref, "--"], cwd=checkout
    )
    if result.returncode != 0:
        raise RefNotFound(f"ref {ref!r} not found: {result.stderr.strip()}")
    return checkout


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
            tree[key] = _sha256_file(full)
    return tree


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
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


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
