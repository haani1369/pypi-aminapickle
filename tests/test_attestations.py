import base64
import json
from pathlib import Path

import pytest

from pypi_aminapickle.attestations import (
    AttestedSource,
    provenance_url,
    resolve_attested_source,
)
from pypi_aminapickle.errors import (
    AttestationError,
    FetchError,
    PypiAminapickleError,
)
from pypi_aminapickle.pypi import Fetcher

FIXTURE = (
    Path(__file__).parent / "fixtures" / "provenance_cryptography_44.0.0.json"
)
NAME = "cryptography"
VERSION = "44.0.0"
FILENAME = "cryptography-44.0.0.tar.gz"
COMMIT = "f299a48153650f2dd87716343f2daa7cd39a1f59"
REPO = "https://github.com/pyca/cryptography"


def fixture_bytes() -> bytes:
    return FIXTURE.read_bytes()


def fixture_sha256() -> str:
    data = json.loads(fixture_bytes())
    envelope = data["attestation_bundles"][0]["attestations"][0]["envelope"]
    statement = json.loads(base64.b64decode(envelope["statement"]))
    sha256 = statement["subject"][0]["digest"]["sha256"]
    assert isinstance(sha256, str)
    return sha256


def make_fetch(mapping: dict[str, bytes]) -> Fetcher:
    def fetch(url: str) -> bytes:
        if url not in mapping:
            raise FetchError(f"404 {url}")
        return mapping[url]

    return fetch


def test_provenance_url_encodes() -> None:
    url = provenance_url("a b", "1.0+x", "f n.tar.gz")
    assert url == (
        "https://pypi.org/integrity/a%20b/1.0%2Bx/f%20n.tar.gz/provenance"
    )


def test_resolve_from_fixture() -> None:
    url = provenance_url(NAME, VERSION, FILENAME)
    fetch = make_fetch({url: fixture_bytes()})
    source = resolve_attested_source(
        NAME, VERSION, FILENAME, fixture_sha256(), fetch
    )
    assert source == AttestedSource(repo_url=REPO, commit=COMMIT)


def test_subject_mismatch_raises() -> None:
    url = provenance_url(NAME, VERSION, FILENAME)
    fetch = make_fetch({url: fixture_bytes()})
    with pytest.raises(AttestationError):
        resolve_attested_source(NAME, VERSION, FILENAME, "0" * 64, fetch)


def test_no_provenance_returns_none() -> None:
    fetch = make_fetch({})
    result = resolve_attested_source(NAME, VERSION, FILENAME, "0" * 64, fetch)
    assert result is None


def test_empty_bundles_returns_none() -> None:
    url = provenance_url(NAME, VERSION, FILENAME)
    body = json.dumps({"version": 1, "attestation_bundles": []}).encode()
    fetch = make_fetch({url: body})
    result = resolve_attested_source(NAME, VERSION, FILENAME, "0" * 64, fetch)
    assert result is None


def test_bad_certificate_raises() -> None:
    sha = "a" * 64
    statement = base64.b64encode(
        json.dumps({"subject": [{"digest": {"sha256": sha}}]}).encode()
    ).decode()
    body = json.dumps(
        {
            "attestation_bundles": [
                {
                    "publisher": {},
                    "attestations": [
                        {
                            "envelope": {
                                "statement": statement,
                                "signature": "x",
                            },
                            "verification_material": {
                                "certificate": "notacert"
                            },
                        }
                    ],
                }
            ]
        }
    ).encode()
    url = provenance_url(NAME, VERSION, FILENAME)
    fetch = make_fetch({url: body})
    with pytest.raises(AttestationError):
        resolve_attested_source(NAME, VERSION, FILENAME, sha, fetch)


def test_error_hierarchy() -> None:
    assert issubclass(AttestationError, PypiAminapickleError)
