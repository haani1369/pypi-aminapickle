import hashlib
import io
import json
import os
import tarfile
from collections.abc import Callable

from srcverify.pypi import Fetcher, metadata_url
from srcverify.requirements import PinnedRequirement
from srcverify.verify import verify_package

REQ = PinnedRequirement(name="pkg", version="1.0")
SDIST_URL = "https://files.example/pkg-1.0.tar.gz"
GITHUB = {"Source": "https://github.com/o/r"}
SDIST_SOURCE = {"a.py": b"alpha\n", "pkg/b.py": b"beta\n"}


def sdist_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for rel, data in {**files, "PKG-INFO": b"generated\n"}.items():
            info = tarfile.TarInfo(f"pkg-1.0/{rel}")
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def metadata_bytes(project_urls: dict[str, str], sha: str) -> bytes:
    body = {
        "info": {"name": "pkg", "version": "1.0", "project_urls": project_urls},
        "urls": [
            {
                "filename": "pkg-1.0.tar.gz",
                "url": SDIST_URL,
                "packagetype": "sdist",
                "digests": {"sha256": sha},
            }
        ],
    }
    return json.dumps(body).encode("utf-8")


def make_fetch(project_urls: dict[str, str]) -> Fetcher:
    archive = sdist_bytes(SDIST_SOURCE)
    sha = hashlib.sha256(archive).hexdigest()
    responses = {
        metadata_url("pkg", "1.0"): metadata_bytes(project_urls, sha),
        SDIST_URL: archive,
    }

    def fetch(url: str) -> bytes:
        return responses[url]

    return fetch


def cloner(
    repo_source: dict[str, bytes],
) -> Callable[[str, str, str], str]:
    def clone(url: str, ref: str, dest_dir: str) -> str:
        checkout = os.path.join(dest_dir, "repo")
        for rel, data in repo_source.items():
            full = os.path.join(checkout, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as handle:
                handle.write(data)
        return checkout

    return clone


def raising_clone(url: str, ref: str, dest_dir: str) -> str:
    raise AssertionError("clone should not be reached")


def test_match() -> None:
    result = verify_package(
        REQ,
        fetch=make_fetch(GITHUB),
        list_refs=lambda url: ["v1.0"],
        clone=cloner(SDIST_SOURCE),
    )
    assert result.status == "match"
    assert result.repo_url == "https://github.com/o/r"
    assert result.ref == "v1.0"
    assert result.findings == []


def test_mismatch_altered_file() -> None:
    altered = {"a.py": b"TAMPERED\n", "pkg/b.py": b"beta\n"}
    result = verify_package(
        REQ,
        fetch=make_fetch(GITHUB),
        list_refs=lambda url: ["v1.0"],
        clone=cloner(altered),
    )
    assert result.status == "mismatch"
    assert [(f.kind, f.path) for f in result.findings] == [("altered", "a.py")]
    assert result.repo_url == "https://github.com/o/r"
    assert result.ref == "v1.0"


def test_unverified_bad_metadata() -> None:
    def fetch(url: str) -> bytes:
        return b"not json"

    result = verify_package(
        REQ,
        fetch=fetch,
        list_refs=lambda url: ["v1.0"],
        clone=raising_clone,
    )
    assert result.status == "unverified"
    assert result.repo_url is None


def test_unverified_no_source_repo() -> None:
    result = verify_package(
        REQ,
        fetch=make_fetch({"Homepage": "https://example.com/pkg"}),
        list_refs=lambda url: ["v1.0"],
        clone=raising_clone,
    )
    assert result.status == "unverified"
    assert result.repo_url is None


def test_unverified_unresolvable_ref() -> None:
    result = verify_package(
        REQ,
        fetch=make_fetch(GITHUB),
        list_refs=lambda url: ["main"],
        clone=raising_clone,
    )
    assert result.status == "unverified"
    assert result.repo_url == "https://github.com/o/r"
    assert result.ref is None
