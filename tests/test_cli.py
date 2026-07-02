import io
import json
import time
from collections.abc import Callable
from pathlib import Path

from pypi_aminapickle.cli import run
from pypi_aminapickle.report import PackageResult
from pypi_aminapickle.requirements import PinnedRequirement


def make_verifier(
    status: str,
) -> Callable[[PinnedRequirement], PackageResult]:
    def verify(req: PinnedRequirement) -> PackageResult:
        return PackageResult(
            name=req.name,
            version=req.version,
            status=status,
            reason="reason",
            repo_url="https://github.com/o/r",
            ref="v1.0",
            findings=[],
        )

    return verify


def write_reqs(tmp_path: Path, text: str) -> str:
    path = tmp_path / "requirements.txt"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_all_match_returns_zero(tmp_path: Path) -> None:
    path = write_reqs(tmp_path, "pkg==1.0\n")
    out, err = io.StringIO(), io.StringIO()
    code = run([path], verify=make_verifier("match"), stdout=out, stderr=err)
    assert code == 0
    assert "[MATCH] pkg==1.0" in out.getvalue()


def test_mismatch_returns_one(tmp_path: Path) -> None:
    path = write_reqs(tmp_path, "pkg==1.0\n")
    out, err = io.StringIO(), io.StringIO()
    code = run([path], verify=make_verifier("mismatch"), stdout=out, stderr=err)
    assert code == 1


def test_json_output(tmp_path: Path) -> None:
    path = write_reqs(tmp_path, "pkg==1.0\n")
    out, err = io.StringIO(), io.StringIO()
    code = run(
        [path, "--json"],
        verify=make_verifier("match"),
        stdout=out,
        stderr=err,
    )
    assert code == 0
    payload = json.loads(out.getvalue())
    assert payload["ok"] is True
    assert payload["results"][0]["name"] == "pkg"


def test_unpinned_returns_two(tmp_path: Path) -> None:
    path = write_reqs(tmp_path, "pkg\n")
    out, err = io.StringIO(), io.StringIO()
    code = run([path], verify=make_verifier("match"), stdout=out, stderr=err)
    assert code == 2
    assert err.getvalue().strip()


def test_missing_file_returns_two(tmp_path: Path) -> None:
    out, err = io.StringIO(), io.StringIO()
    code = run(
        [str(tmp_path / "nope.txt")],
        verify=make_verifier("match"),
        stdout=out,
        stderr=err,
    )
    assert code == 2


def reordering_verifier() -> Callable[[PinnedRequirement], PackageResult]:
    # earlier-listed packages finish later, so completion order differs
    # from file order; the report must still be in file order
    delays = {"a": 0.03, "b": 0.015, "c": 0.0}

    def verify(req: PinnedRequirement) -> PackageResult:
        time.sleep(delays.get(req.name, 0.0))
        return PackageResult(
            name=req.name,
            version=req.version,
            status="match",
            reason="reason",
            repo_url="https://github.com/o/r",
            ref="v1.0",
            findings=[],
        )

    return verify


def reported_names(output: str) -> list[str]:
    names = []
    for line in output.splitlines():
        if line.startswith("[MATCH] "):
            names.append(line.split(" ", 2)[1].split("==")[0])
    return names


def test_parallel_reports_in_file_order(tmp_path: Path) -> None:
    path = write_reqs(tmp_path, "a==1.0\nb==1.0\nc==1.0\n")
    out, err = io.StringIO(), io.StringIO()
    code = run([path], verify=reordering_verifier(), stdout=out, stderr=err)
    assert code == 0
    assert reported_names(out.getvalue()) == ["a", "b", "c"]


def test_jobs_one_reports_in_file_order(tmp_path: Path) -> None:
    path = write_reqs(tmp_path, "a==1.0\nb==1.0\nc==1.0\n")
    out, err = io.StringIO(), io.StringIO()
    code = run(
        [path, "--jobs", "1"],
        verify=reordering_verifier(),
        stdout=out,
        stderr=err,
    )
    assert code == 0
    assert reported_names(out.getvalue()) == ["a", "b", "c"]
