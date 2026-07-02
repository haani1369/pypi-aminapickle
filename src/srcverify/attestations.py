"""resolve source repo and commit from pep 740 provenance."""

import base64
import json
from dataclasses import dataclass
from urllib.parse import quote

from cryptography import x509

from srcverify.errors import AttestationError, FetchError, InvalidRepoUrl
from srcverify.pypi import Fetcher
from srcverify.repo import validate_repo_url

_SOURCE_URI_OID = "1.3.6.1.4.1.57264.1.12"
_SOURCE_DIGEST_OID = "1.3.6.1.4.1.57264.1.13"


@dataclass(frozen=True)
class AttestedSource:
    repo_url: str
    commit: str


def provenance_url(name: str, version: str, filename: str) -> str:
    return (
        "https://pypi.org/integrity/"
        f"{quote(name, safe='')}/"
        f"{quote(version, safe='')}/"
        f"{quote(filename, safe='')}/provenance"
    )


def resolve_attested_source(
    name: str,
    version: str,
    filename: str,
    sdist_sha256: str,
    fetch: Fetcher,
) -> AttestedSource | None:
    try:
        body = fetch(provenance_url(name, version, filename))
    except FetchError:
        return None
    attestation = _first_attestation(body)
    if attestation is None:
        return None
    envelope, material = attestation
    subject = _subject_sha256(envelope)
    if subject != sdist_sha256.lower():
        raise AttestationError(
            f"attestation subject {subject} != sdist {sdist_sha256.lower()}"
        )
    uri, commit = _source_from_cert(material)
    try:
        repo_url = validate_repo_url(uri)
    except InvalidRepoUrl as exc:
        raise AttestationError(f"attested source uri invalid: {exc}") from exc
    repo_url = repo_url.rstrip("/")
    if repo_url.endswith(".git"):
        repo_url = repo_url[: -len(".git")]
    return AttestedSource(repo_url=repo_url, commit=commit)


def _first_attestation(
    body: bytes,
) -> tuple[dict[str, object], dict[str, object]] | None:
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AttestationError(f"provenance is not json: {exc}") from exc
    if not isinstance(data, dict):
        raise AttestationError("provenance is not an object")
    bundles = data.get("attestation_bundles")
    if not isinstance(bundles, list):
        return None
    for bundle in bundles:
        if not isinstance(bundle, dict):
            continue
        attestations = bundle.get("attestations")
        if not isinstance(attestations, list):
            continue
        for attestation in attestations:
            if not isinstance(attestation, dict):
                continue
            envelope = attestation.get("envelope")
            material = attestation.get("verification_material")
            if isinstance(envelope, dict) and isinstance(material, dict):
                return envelope, material
    return None


def _subject_sha256(envelope: dict[str, object]) -> str:
    statement_b64 = envelope.get("statement")
    if not isinstance(statement_b64, str):
        raise AttestationError("envelope has no statement")
    try:
        statement = json.loads(base64.b64decode(statement_b64))
    except (ValueError, json.JSONDecodeError) as exc:
        raise AttestationError(f"unreadable statement: {exc}") from exc
    if not isinstance(statement, dict):
        raise AttestationError("statement is not an object")
    subjects = statement.get("subject")
    if (
        not isinstance(subjects, list)
        or not subjects
        or not isinstance(subjects[0], dict)
    ):
        raise AttestationError("statement has no subject")
    digest = subjects[0].get("digest")
    if not isinstance(digest, dict):
        raise AttestationError("subject has no digest")
    sha256 = digest.get("sha256")
    if not isinstance(sha256, str):
        raise AttestationError("subject digest has no sha256")
    return sha256.lower()


def _source_from_cert(material: dict[str, object]) -> tuple[str, str]:
    certificate = material.get("certificate")
    if not isinstance(certificate, str):
        raise AttestationError("no certificate in verification material")
    try:
        cert = x509.load_der_x509_certificate(base64.b64decode(certificate))
    except (ValueError, TypeError) as exc:
        raise AttestationError(f"unparseable certificate: {exc}") from exc
    uri = _extension_string(cert, _SOURCE_URI_OID)
    commit = _extension_string(cert, _SOURCE_DIGEST_OID)
    if not uri or not commit:
        raise AttestationError("certificate lacks source repo extensions")
    return uri, commit


def _extension_string(cert: x509.Certificate, oid: str) -> str | None:
    try:
        extension = cert.extensions.get_extension_for_oid(
            x509.ObjectIdentifier(oid)
        )
    except x509.ExtensionNotFound:
        return None
    value = extension.value
    if not isinstance(value, x509.UnrecognizedExtension):
        return None
    return _der_utf8(value.value)


def _der_utf8(raw: bytes) -> str | None:
    if len(raw) < 2 or raw[0] != 0x0C:
        return None
    length = raw[1]
    offset = 2
    if length & 0x80:
        count = length & 0x7F
        length = int.from_bytes(raw[2 : 2 + count], "big")
        offset = 2 + count
    data = raw[offset : offset + length]
    if len(data) != length:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None
