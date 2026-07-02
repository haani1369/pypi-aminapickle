import io
from pathlib import Path

import pytest

from srcverify.attestations import resolve_attested_source
from srcverify.cli import run
from srcverify.pypi import default_fetcher
from srcverify.requirements import PinnedRequirement
from srcverify.verify import verify_package

pytestmark = pytest.mark.integration

_STATUSES = {"match", "mismatch", "unverified"}


def test_live_attestation_resolves() -> None:
    source = resolve_attested_source(
        "cryptography",
        "44.0.0",
        "cryptography-44.0.0.tar.gz",
        "cd4e834f340b4293430701e772ec543b0fbe6c2dea510a5286fe0acabe153a02",
        default_fetcher,
    )
    assert source is not None
    assert source.repo_url == "https://github.com/pyca/cryptography"
    assert len(source.commit) == 40


def test_verify_real_package_completes() -> None:
    result = verify_package(PinnedRequirement(name="click", version="8.1.7"))
    assert result.status in _STATUSES
    if result.status != "unverified":
        assert result.repo_url is not None
        assert result.repo_url.startswith("https://")


def test_cli_real_requirements_gate(tmp_path: Path) -> None:
    path = tmp_path / "requirements.txt"
    path.write_text("click==8.1.7\n", encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    code = run([str(path)], verify=verify_package, stdout=out, stderr=err)
    assert code in (0, 1)
    assert out.getvalue().strip()
