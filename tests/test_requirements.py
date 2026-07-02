from pathlib import Path

import pytest
from srcverify.errors import (
    ConflictingPins,
    MalformedRequirement,
    RequirementsError,
    SrcverifyError,
    UnpinnedRequirement,
    UnsupportedRequirementLine,
)
from srcverify.requirements import (
    PinnedRequirement,
    load_requirements,
    parse_requirements,
)


@pytest.mark.parametrize(
    ("line", "name", "version"),
    [
        ("requests==2.31.0", "requests", "2.31.0"),
        ("Flask==3.0.0", "flask", "3.0.0"),
        ("pyyaml==6.0.1", "pyyaml", "6.0.1"),
        ("uvicorn[standard]==0.30.1", "uvicorn", "0.30.1"),
        (
            'httpx==0.27.0 ; python_version >= "3.8"',
            "httpx",
            "0.27.0",
        ),
    ],
)
def test_accepted_examples(line: str, name: str, version: str) -> None:
    result = parse_requirements(line)
    assert result == [PinnedRequirement(name=name, version=version)]


@pytest.mark.parametrize(
    ("line", "name"),
    [
        ("Flask==3.0.0", "flask"),
        ("Foo_Bar.baz==1.0.0", "foo-bar-baz"),
    ],
)
def test_name_canonicalization(line: str, name: str) -> None:
    result = parse_requirements(line)
    assert result[0].name == name


def test_extras_ignored() -> None:
    result = parse_requirements("uvicorn[standard]==0.30.1")
    assert result == [PinnedRequirement(name="uvicorn", version="0.30.1")]


def test_environment_marker_allowed_not_evaluated() -> None:
    line = 'httpx==0.27.0 ; python_version < "3.0"'
    result = parse_requirements(line)
    assert result == [PinnedRequirement(name="httpx", version="0.27.0")]


def test_inline_comment_stripped() -> None:
    result = parse_requirements("requests==2.31.0  # pinned")
    assert result == [PinnedRequirement(name="requests", version="2.31.0")]


def test_full_line_comment_skipped() -> None:
    text = "# a comment\nrequests==2.31.0\n"
    result = parse_requirements(text)
    assert result == [PinnedRequirement(name="requests", version="2.31.0")]


def test_blank_lines_skipped() -> None:
    text = "\n\nrequests==2.31.0\n   \n"
    result = parse_requirements(text)
    assert result == [PinnedRequirement(name="requests", version="2.31.0")]


def test_backslash_line_continuation() -> None:
    text = "requests==\\\n2.31.0\n"
    result = parse_requirements(text)
    assert result == [PinnedRequirement(name="requests", version="2.31.0")]


def test_first_seen_order_preserved() -> None:
    text = "flask==3.0.0\nrequests==2.31.0\nhttpx==0.27.0\n"
    result = parse_requirements(text)
    assert result == [
        PinnedRequirement(name="flask", version="3.0.0"),
        PinnedRequirement(name="requests", version="2.31.0"),
        PinnedRequirement(name="httpx", version="0.27.0"),
    ]


def test_duplicate_identical_pins_collapse() -> None:
    text = "requests==2.31.0\nrequests==2.31.0\n"
    result = parse_requirements(text)
    assert result == [PinnedRequirement(name="requests", version="2.31.0")]


@pytest.mark.parametrize(
    "line",
    [
        "requests",
        "requests>=2.0",
        "requests==2.*",
        "requests===2.31.0",
    ],
)
def test_unpinned_requirement(line: str) -> None:
    with pytest.raises(UnpinnedRequirement):
        parse_requirements(line)


@pytest.mark.parametrize(
    "line",
    [
        "==1.0",
        "requests==2.31.0 and flask==3",
    ],
)
def test_malformed_requirement(line: str) -> None:
    with pytest.raises(MalformedRequirement):
        parse_requirements(line)


@pytest.mark.parametrize(
    "line",
    [
        "-r base.txt",
        "-e .",
        "./local/pkg",
        "pkg @ git+https://x/y.git",
        "http://example.com/pkg-1.0.tar.gz",
    ],
)
def test_unsupported_requirement_line(line: str) -> None:
    with pytest.raises(UnsupportedRequirementLine):
        parse_requirements(line)


def test_conflicting_pins() -> None:
    text = "requests==2.31.0\nrequests==2.32.0\n"
    with pytest.raises(ConflictingPins):
        parse_requirements(text)


def test_errors_subclass_hierarchy() -> None:
    assert issubclass(RequirementsError, SrcverifyError)
    for error in (
        UnpinnedRequirement,
        MalformedRequirement,
        UnsupportedRequirementLine,
        ConflictingPins,
    ):
        assert issubclass(error, RequirementsError)


def test_load_requirements_matches_parse(tmp_path: Path) -> None:
    text = "flask==3.0.0\nrequests==2.31.0\n"
    path = tmp_path / "requirements.txt"
    path.write_text(text, encoding="utf-8")
    assert load_requirements(str(path)) == parse_requirements(text)


def test_load_requirements_missing_path() -> None:
    with pytest.raises(FileNotFoundError):
        load_requirements("/nonexistent/requirements.txt")
