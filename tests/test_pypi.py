import hashlib
import json
from pathlib import Path

import pytest
from srcverify.pypi import (
    ArtifactRef,
    Fetcher,
    Metadata,
    Sdist,
    default_fetcher,
    download_sdist,
    fetch_metadata,
    metadata_url,
    select_sdist,
)

from srcverify.errors import (
    FetchError,
    IntegrityError,
    MetadataError,
    NoSdist,
    PypiError,
    SrcverifyError,
)


def make_fetcher(responses: dict[str, bytes]) -> Fetcher:
    def fetch(url: str) -> bytes:
        return responses[url]

    return fetch


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_entry(
    filename: str,
    url: str,
    packagetype: str,
    sha256: str,
) -> dict[str, object]:
    return {
        "filename": filename,
        "url": url,
        "packagetype": packagetype,
        "digests": {"sha256": sha256},
    }


def metadata_body(
    project_urls: object,
    urls: object,
    name: str = "requests",
    version: str = "2.31.0",
) -> bytes:
    info: dict[str, object] = {"name": name, "version": version}
    if project_urls is not None:
        info["project_urls"] = project_urls
    body: dict[str, object] = {"info": info, "urls": urls}
    return json.dumps(body).encode("utf-8")


def test_metadata_url_percent_encodes() -> None:
    url = metadata_url("foo bar", "1.0+local")
    assert url == "https://pypi.org/pypi/foo%20bar/1.0%2Blocal/json"


def test_fetch_metadata_valid() -> None:
    project_urls = {"Source": "https://github.com/psf/requests"}
    urls = [
        file_entry(
            "requests-2.31.0.tar.gz",
            "https://files.pythonhosted.org/requests-2.31.0.tar.gz",
            "sdist",
            "a" * 64,
        ),
        file_entry(
            "requests-2.31.0-py3-none-any.whl",
            "https://files.pythonhosted.org/requests-2.31.0.whl",
            "bdist_wheel",
            "b" * 64,
        ),
    ]
    body = metadata_body(project_urls, urls)
    url = metadata_url("requests", "2.31.0")
    fetch = make_fetcher({url: body})
    metadata = fetch_metadata("requests", "2.31.0", fetch)
    assert metadata.name == "requests"
    assert metadata.version == "2.31.0"
    assert metadata.project_urls == project_urls
    assert metadata.artifacts == [
        ArtifactRef(
            filename="requests-2.31.0.tar.gz",
            url="https://files.pythonhosted.org/requests-2.31.0.tar.gz",
            packagetype="sdist",
            sha256="a" * 64,
        ),
        ArtifactRef(
            filename="requests-2.31.0-py3-none-any.whl",
            url="https://files.pythonhosted.org/requests-2.31.0.whl",
            packagetype="bdist_wheel",
            sha256="b" * 64,
        ),
    ]


def test_fetch_metadata_non_json() -> None:
    url = metadata_url("requests", "2.31.0")
    fetch = make_fetcher({url: b"not json at all"})
    with pytest.raises(MetadataError):
        fetch_metadata("requests", "2.31.0", fetch)


def test_fetch_metadata_json_array() -> None:
    url = metadata_url("requests", "2.31.0")
    fetch = make_fetcher({url: json.dumps([1, 2, 3]).encode("utf-8")})
    with pytest.raises(MetadataError):
        fetch_metadata("requests", "2.31.0", fetch)


def test_fetch_metadata_missing_urls() -> None:
    url = metadata_url("requests", "2.31.0")
    body = json.dumps({"info": {"name": "requests"}}).encode("utf-8")
    fetch = make_fetcher({url: body})
    with pytest.raises(MetadataError):
        fetch_metadata("requests", "2.31.0", fetch)


def test_fetch_metadata_skips_malformed_entry() -> None:
    urls = [
        {"filename": "broken.tar.gz", "packagetype": "sdist"},
        file_entry(
            "requests-2.31.0.tar.gz",
            "https://files.pythonhosted.org/requests-2.31.0.tar.gz",
            "sdist",
            "a" * 64,
        ),
    ]
    body = metadata_body({}, urls)
    url = metadata_url("requests", "2.31.0")
    fetch = make_fetcher({url: body})
    metadata = fetch_metadata("requests", "2.31.0", fetch)
    assert metadata.artifacts == [
        ArtifactRef(
            filename="requests-2.31.0.tar.gz",
            url="https://files.pythonhosted.org/requests-2.31.0.tar.gz",
            packagetype="sdist",
            sha256="a" * 64,
        )
    ]


def test_fetch_metadata_empty_project_urls_when_not_object() -> None:
    urls = [
        file_entry(
            "requests-2.31.0.tar.gz",
            "https://files.pythonhosted.org/requests-2.31.0.tar.gz",
            "sdist",
            "a" * 64,
        )
    ]
    body = metadata_body("not-an-object", urls)
    url = metadata_url("requests", "2.31.0")
    fetch = make_fetcher({url: body})
    metadata = fetch_metadata("requests", "2.31.0", fetch)
    assert metadata.project_urls == {}


def make_metadata(artifacts: list[ArtifactRef]) -> Metadata:
    return Metadata(
        name="requests",
        version="2.31.0",
        project_urls={},
        artifacts=artifacts,
    )


def test_select_sdist_single() -> None:
    sdist = ArtifactRef("pkg-1.0.tar.gz", "https://x/pkg.tar.gz", "sdist", "a")
    wheel = ArtifactRef("pkg-1.0.whl", "https://x/pkg.whl", "bdist_wheel", "b")
    metadata = make_metadata([sdist, wheel])
    assert select_sdist(metadata) == sdist


def test_select_sdist_none() -> None:
    wheel = ArtifactRef("pkg-1.0.whl", "https://x/pkg.whl", "bdist_wheel", "b")
    metadata = make_metadata([wheel])
    with pytest.raises(NoSdist):
        select_sdist(metadata)


def test_select_sdist_two_one_tar_gz() -> None:
    tar = ArtifactRef("pkg-1.0.tar.gz", "https://x/pkg.tar.gz", "sdist", "a")
    zip_ = ArtifactRef("pkg-1.0.zip", "https://x/pkg.zip", "sdist", "b")
    metadata = make_metadata([tar, zip_])
    assert select_sdist(metadata) == tar


def test_select_sdist_two_tar_gz() -> None:
    a = ArtifactRef("pkg-1.0.tar.gz", "https://x/a.tar.gz", "sdist", "a")
    b = ArtifactRef("pkg-1.0.post0.tar.gz", "https://x/b.tar.gz", "sdist", "b")
    metadata = make_metadata([a, b])
    with pytest.raises(NoSdist):
        select_sdist(metadata)


def test_download_sdist_success(tmp_path: Path) -> None:
    data = b"sdist bytes"
    ref = ArtifactRef(
        filename="pkg-1.0.tar.gz",
        url="https://x/pkg-1.0.tar.gz",
        packagetype="sdist",
        sha256=sha256_hex(data),
    )
    fetch = make_fetcher({ref.url: data})
    sdist = download_sdist(ref, str(tmp_path), fetch)
    assert isinstance(sdist, Sdist)
    assert sdist.ref == ref
    path = Path(sdist.path)
    assert path.exists()
    assert path.read_bytes() == data
    assert path.parent == tmp_path


def test_download_sdist_integrity_mismatch(tmp_path: Path) -> None:
    ref = ArtifactRef(
        filename="pkg-1.0.tar.gz",
        url="https://x/pkg-1.0.tar.gz",
        packagetype="sdist",
        sha256="0" * 64,
    )
    fetch = make_fetcher({ref.url: b"other bytes"})
    with pytest.raises(IntegrityError):
        download_sdist(ref, str(tmp_path), fetch)
    assert list(tmp_path.iterdir()) == []


def test_download_sdist_strips_path_separator(tmp_path: Path) -> None:
    data = b"sdist bytes"
    ref = ArtifactRef(
        filename="../evil.tar.gz",
        url="https://x/evil.tar.gz",
        packagetype="sdist",
        sha256=sha256_hex(data),
    )
    fetch = make_fetcher({ref.url: data})
    sdist = download_sdist(ref, str(tmp_path), fetch)
    path = Path(sdist.path)
    assert path.parent == tmp_path
    assert path.name == "evil.tar.gz"
    assert path.read_bytes() == data


def test_error_hierarchy() -> None:
    assert issubclass(PypiError, SrcverifyError)
    for error in (FetchError, MetadataError, NoSdist, IntegrityError):
        assert issubclass(error, PypiError)


def test_default_fetcher_non_https_raises() -> None:
    with pytest.raises(FetchError):
        default_fetcher("http://example.com")
