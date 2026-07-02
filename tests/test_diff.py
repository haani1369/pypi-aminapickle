from srcverify.diff import Finding, diff_trees


def test_identical_trees_no_findings() -> None:
    tree = {"a.py": "1", "pkg/b.py": "2"}
    assert diff_trees(tree, dict(tree)) == []


def test_sdist_only_path_is_extra() -> None:
    findings = diff_trees({"a.py": "1", "evil.py": "9"}, {"a.py": "1"})
    assert findings == [Finding(kind="extra", path="evil.py")]


def test_shared_path_differing_digest_is_altered() -> None:
    findings = diff_trees({"a.py": "9"}, {"a.py": "1"})
    assert findings == [Finding(kind="altered", path="a.py")]


def test_repo_only_path_no_finding() -> None:
    assert diff_trees({"a.py": "1"}, {"a.py": "1", "tests/t.py": "2"}) == []


def test_pkg_info_ignored() -> None:
    assert diff_trees({"PKG-INFO": "9"}, {}) == []


def test_egg_info_ignored() -> None:
    sdist = {
        "src/pkg.egg-info/PKG-INFO": "9",
        "src/pkg.egg-info/SOURCES.txt": "8",
    }
    assert diff_trees(sdist, {}) == []


def test_mixed_sorted_by_path_then_kind() -> None:
    sdist = {
        "z.py": "9",
        "a.py": "9",
        "keep.py": "1",
        "PKG-INFO": "0",
    }
    repo = {"a.py": "1", "keep.py": "1"}
    assert diff_trees(sdist, repo) == [
        Finding(kind="altered", path="a.py"),
        Finding(kind="extra", path="z.py"),
    ]


def test_altered_not_double_reported_as_extra() -> None:
    findings = diff_trees({"a.py": "9"}, {"a.py": "1"})
    assert len(findings) == 1
    assert findings[0].kind == "altered"
