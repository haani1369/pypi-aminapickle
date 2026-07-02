import json

from pypi_aminapickle.diff import Finding
from pypi_aminapickle.report import (
    PackageResult,
    all_match,
    render_json,
    render_text,
)


def match_result() -> PackageResult:
    return PackageResult(
        name="requests",
        version="2.31.0",
        status="match",
        reason="matches source",
        repo_url="https://github.com/psf/requests",
        ref="v2.31.0",
        findings=[],
    )


def mismatch_result() -> PackageResult:
    return PackageResult(
        name="foo",
        version="1.0",
        status="mismatch",
        reason="2 differing files",
        repo_url="https://github.com/o/foo",
        ref="v1.0",
        findings=[
            Finding(kind="altered", path="foo/core.py"),
            Finding(kind="extra", path="foo/evil.py"),
        ],
    )


def unverified_result() -> PackageResult:
    return PackageResult(
        name="bar",
        version="2.0",
        status="unverified",
        reason="no recognized repository url in metadata",
        repo_url=None,
        ref=None,
        findings=[],
    )


def test_all_match_true_only_when_all_match() -> None:
    assert all_match([match_result(), match_result()])
    assert not all_match([match_result(), mismatch_result()])
    assert not all_match([match_result(), unverified_result()])


def test_render_json_structure() -> None:
    results = [match_result(), mismatch_result(), unverified_result()]
    payload = json.loads(render_json(results))
    assert payload["ok"] is False
    assert [r["status"] for r in payload["results"]] == [
        "match",
        "mismatch",
        "unverified",
    ]
    assert payload["results"][2]["repo_url"] is None
    assert payload["results"][2]["ref"] is None
    assert payload["results"][1]["findings"] == [
        {"kind": "altered", "path": "foo/core.py"},
        {"kind": "extra", "path": "foo/evil.py"},
    ]


def test_render_json_ok_true_when_all_match() -> None:
    payload = json.loads(render_json([match_result()]))
    assert payload["ok"] is True


def test_render_text_tags_and_target() -> None:
    text = render_text([match_result()])
    assert "[MATCH] requests==2.31.0" in text
    assert "https://github.com/psf/requests@v2.31.0" in text


def test_render_text_mismatch_findings_and_reason() -> None:
    text = render_text([mismatch_result()])
    assert "[MISMATCH] foo==1.0" in text
    assert "(2 differing files)" in text
    assert "    altered: foo/core.py" in text
    assert "    extra: foo/evil.py" in text


def test_render_text_unverified_has_no_target() -> None:
    text = render_text([unverified_result()])
    assert "[UNVERIFIED] bar==2.0" in text
    assert "@" not in text.splitlines()[0]


def test_render_text_summary_counts() -> None:
    text = render_text([match_result(), mismatch_result(), unverified_result()])
    assert "3 packages: 1 match, 1 mismatch, 1 unverified" in text.splitlines()
