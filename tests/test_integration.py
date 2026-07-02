import io
from pathlib import Path

import pytest

from srcverify.cli import run
from srcverify.requirements import PinnedRequirement
from srcverify.verify import verify_package

pytestmark = pytest.mark.integration

_STATUSES = {"match", "mismatch", "unverified"}


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
