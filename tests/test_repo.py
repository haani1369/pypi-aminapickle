import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from srcverify.errors import (
    CloneError,
    InvalidRepoUrl,
    RefNotFound,
    RepoError,
    SrcverifyError,
)
from srcverify.repo import (
    clone_repo,
    list_remote_refs,
    repo_files,
    validate_repo_url,
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return env


def git(cwd: str, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=git_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


README = b"# readme\nhello\n"
MOD = b"x = 1\n"


def make_repo(tmp_path: Path) -> tuple[str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    repo_path = str(repo)
    git(repo_path, "init")
    (repo / "README.md").write_bytes(README)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "mod.py").write_bytes(MOD)
    git(repo_path, "add", "-A")
    git(repo_path, "commit", "-m", "initial")
    git(repo_path, "tag", "v1.0.0")
    commit_sha = git(repo_path, "rev-parse", "HEAD").strip()
    return repo_path, commit_sha


def fresh_dir(tmp_path: Path, name: str) -> str:
    dest = tmp_path / name
    dest.mkdir()
    return str(dest)


EXPECTED_TREE = {
    "README.md": sha256_hex(README),
    "pkg/mod.py": sha256_hex(MOD),
}


def test_accepts_https_github_url() -> None:
    url = "https://github.com/psf/requests"
    assert validate_repo_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/x/y",
        "file:///etc/passwd",
        "ext::sh -c id",
        "git@github.com:o/r.git",
        "-oProxyCommand=x",
        "https://",
    ],
)
def test_rejects_bad_url(url: str) -> None:
    with pytest.raises(InvalidRepoUrl):
        validate_repo_url(url)


def test_clone_at_tag(tmp_path: Path) -> None:
    repo_path, _ = make_repo(tmp_path)
    dest = fresh_dir(tmp_path, "dest")
    checkout = clone_repo(repo_path, "v1.0.0", dest)
    assert repo_files(checkout) == EXPECTED_TREE


def test_clone_at_commit_sha(tmp_path: Path) -> None:
    repo_path, commit_sha = make_repo(tmp_path)
    dest = fresh_dir(tmp_path, "dest")
    checkout = clone_repo(repo_path, commit_sha, dest)
    assert repo_files(checkout) == EXPECTED_TREE


def test_git_dir_excluded(tmp_path: Path) -> None:
    repo_path, _ = make_repo(tmp_path)
    dest = fresh_dir(tmp_path, "dest")
    checkout = clone_repo(repo_path, "v1.0.0", dest)
    for path in repo_files(checkout):
        assert not path.startswith(".git/")


def test_symlink_skipped(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    repo_path = str(repo)
    git(repo_path, "init")
    (repo / "README.md").write_bytes(README)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "mod.py").write_bytes(MOD)
    os.symlink("README.md", repo / "link")
    git(repo_path, "add", "-A")
    git(repo_path, "commit", "-m", "with symlink")
    git(repo_path, "tag", "v1.0.0")

    dest = fresh_dir(tmp_path, "dest")
    checkout = clone_repo(repo_path, "v1.0.0", dest)
    files = repo_files(checkout)
    assert "link" not in files
    assert files == EXPECTED_TREE


def test_nonexistent_ref(tmp_path: Path) -> None:
    repo_path, _ = make_repo(tmp_path)
    dest = fresh_dir(tmp_path, "dest")
    with pytest.raises(RefNotFound):
        clone_repo(repo_path, "v9.9.9", dest)


def test_not_a_repo(tmp_path: Path) -> None:
    src = fresh_dir(tmp_path, "notrepo")
    dest = fresh_dir(tmp_path, "dest")
    with pytest.raises(CloneError):
        clone_repo(src, "v1.0.0", dest)


def test_list_remote_refs_includes_tag(tmp_path: Path) -> None:
    repo_path, _ = make_repo(tmp_path)
    refs = list_remote_refs(repo_path)
    assert "v1.0.0" in refs


def test_list_remote_refs_rejects_option_url() -> None:
    with pytest.raises(InvalidRepoUrl):
        list_remote_refs("--upload-pack=x")


def test_list_remote_refs_not_a_repo(tmp_path: Path) -> None:
    src = fresh_dir(tmp_path, "notrepo")
    with pytest.raises(CloneError):
        list_remote_refs(src)


def test_error_hierarchy() -> None:
    assert issubclass(RepoError, SrcverifyError)
    for error in (InvalidRepoUrl, CloneError, RefNotFound):
        assert issubclass(error, RepoError)
