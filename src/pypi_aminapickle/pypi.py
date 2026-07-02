"""fetch pypi metadata and download the published sdist."""

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pypi_aminapickle.errors import (
    FetchError,
    IntegrityError,
    MetadataError,
    NoSdist,
)

Fetcher = Callable[[str], bytes]

_TIMEOUT = 30.0
_MAX_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class ArtifactRef:
    filename: str
    url: str
    packagetype: str
    sha256: str


@dataclass(frozen=True)
class Metadata:
    name: str
    version: str
    project_urls: dict[str, str]
    artifacts: list[ArtifactRef]


@dataclass(frozen=True)
class Sdist:
    ref: ArtifactRef
    path: str


def default_fetcher(url: str) -> bytes:
    if not url.startswith("https://"):
        raise FetchError(f"refusing non-https url: {url}")
    request = Request(url, headers={"Accept": "*/*"})
    try:
        with urlopen(request, timeout=_TIMEOUT) as response:
            data: bytes = response.read(_MAX_BYTES + 1)
    except URLError as exc:
        raise FetchError(f"failed to fetch {url}: {exc}") from exc
    if len(data) > _MAX_BYTES:
        raise FetchError(f"response exceeds {_MAX_BYTES} bytes: {url}")
    return data


def metadata_url(name: str, version: str) -> str:
    return (
        f"https://pypi.org/pypi/{quote(name, safe='')}/"
        f"{quote(version, safe='')}/json"
    )


def fetch_metadata(name: str, version: str, fetch: Fetcher) -> Metadata:
    body = fetch(metadata_url(name, version))
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise MetadataError(f"metadata is not valid json: {exc}") from exc
    if not isinstance(parsed, dict):
        raise MetadataError("metadata is not a json object")
    info = parsed.get("info")
    if not isinstance(info, dict):
        raise MetadataError("metadata is missing an info object")
    urls = parsed.get("urls")
    if not isinstance(urls, list):
        raise MetadataError("metadata is missing a urls list")
    resolved_name = info.get("name")
    resolved_version = info.get("version")
    return Metadata(
        name=resolved_name if isinstance(resolved_name, str) else name,
        version=(
            resolved_version if isinstance(resolved_version, str) else version
        ),
        project_urls=_string_map(info.get("project_urls")),
        artifacts=[ref for ref in map(_artifact, urls) if ref is not None],
    )


def select_sdist(metadata: Metadata) -> ArtifactRef:
    sdists = [a for a in metadata.artifacts if a.packagetype == "sdist"]
    if not sdists:
        raise NoSdist(f"no sdist for {metadata.name} {metadata.version}")
    if len(sdists) == 1:
        return sdists[0]
    tarballs = [a for a in sdists if a.filename.endswith(".tar.gz")]
    if len(tarballs) == 1:
        return tarballs[0]
    raise NoSdist(f"ambiguous sdist for {metadata.name} {metadata.version}")


def download_sdist(ref: ArtifactRef, dest_dir: str, fetch: Fetcher) -> Sdist:
    filename = os.path.basename(ref.filename)
    if filename in ("", ".", ".."):
        raise IntegrityError(f"unusable sdist filename: {ref.filename!r}")
    data = fetch(ref.url)
    digest = hashlib.sha256(data).hexdigest()
    if digest != ref.sha256.lower():
        raise IntegrityError(
            f"sha256 mismatch for {ref.filename}: "
            f"expected {ref.sha256}, got {digest}"
        )
    path = os.path.join(dest_dir, filename)
    with open(path, "wb") as handle:
        handle.write(data)
    return Sdist(ref=ref, path=path)


def _string_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        key: val
        for key, val in value.items()
        if isinstance(key, str) and isinstance(val, str)
    }


def _artifact(entry: object) -> ArtifactRef | None:
    if not isinstance(entry, dict):
        return None
    filename = entry.get("filename")
    url = entry.get("url")
    packagetype = entry.get("packagetype")
    digests = entry.get("digests")
    if not (
        isinstance(filename, str)
        and isinstance(url, str)
        and isinstance(packagetype, str)
        and isinstance(digests, dict)
    ):
        return None
    sha256 = digests.get("sha256")
    if not isinstance(sha256, str):
        return None
    return ArtifactRef(
        filename=filename,
        url=url,
        packagetype=packagetype,
        sha256=sha256.lower(),
    )
