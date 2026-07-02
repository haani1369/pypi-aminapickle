import pytest

from srcverify.errors import (
    NoSourceRepo,
    SourceError,
    SrcverifyError,
    UnresolvableRef,
)
from srcverify.pypi import Metadata
from srcverify.source import candidate_refs, resolve_repo_url, select_ref


def metadata(project_urls: dict[str, str]) -> Metadata:
    return Metadata(
        name="requests",
        version="2.31.0",
        project_urls=project_urls,
        artifacts=[],
    )


def test_source_github_url_normalized() -> None:
    url = resolve_repo_url(
        metadata({"Source": "https://github.com/psf/requests"})
    )
    assert url == "https://github.com/psf/requests"


def test_preferred_label_beats_earlier_nonpreferred() -> None:
    url = resolve_repo_url(
        metadata(
            {
                "Homepage": "https://github.com/psf/other",
                "Source": "https://gitlab.com/a/b",
            }
        )
    )
    assert url == "https://gitlab.com/a/b"


def test_extra_path_stripped() -> None:
    url = resolve_repo_url(
        metadata({"Source": "https://github.com/psf/requests/issues"})
    )
    assert url == "https://github.com/psf/requests"


def test_tree_path_stripped() -> None:
    url = resolve_repo_url(
        metadata({"Source": "https://github.com/psf/requests/tree/main"})
    )
    assert url == "https://github.com/psf/requests"


def test_dot_git_suffix_stripped() -> None:
    url = resolve_repo_url(
        metadata({"Repository": "https://github.com/psf/requests.git"})
    )
    assert url == "https://github.com/psf/requests"


def test_www_host_normalized() -> None:
    url = resolve_repo_url(
        metadata({"Source": "https://www.github.com/psf/requests"})
    )
    assert url == "https://github.com/psf/requests"


def test_second_pass_finds_unlabeled_repo() -> None:
    url = resolve_repo_url(
        metadata({"Documentation": "https://github.com/psf/requests"})
    )
    assert url == "https://github.com/psf/requests"


def test_non_https_github_not_recognized() -> None:
    with pytest.raises(NoSourceRepo):
        resolve_repo_url(metadata({"Source": "http://github.com/psf/requests"}))


def test_unrecognized_host_raises() -> None:
    with pytest.raises(NoSourceRepo):
        resolve_repo_url(metadata({"Homepage": "https://example.com/foo"}))


def test_empty_project_urls_raises() -> None:
    with pytest.raises(NoSourceRepo):
        resolve_repo_url(metadata({}))


def test_candidate_refs_order() -> None:
    assert candidate_refs("requests", "2.31.0") == [
        "v2.31.0",
        "2.31.0",
        "release-2.31.0",
        "requests-2.31.0",
    ]


def test_select_ref_first_present() -> None:
    assert select_ref(["v1.0.0", "1.0.0"], ["main", "v1.0.0"]) == "v1.0.0"


def test_select_ref_candidate_order_wins() -> None:
    assert select_ref(["1.0.0", "v1.0.0"], ["v1.0.0", "1.0.0"]) == "1.0.0"


def test_select_ref_none_present() -> None:
    with pytest.raises(UnresolvableRef):
        select_ref(["v1.0.0"], ["main", "dev"])


def test_error_hierarchy() -> None:
    assert issubclass(SourceError, SrcverifyError)
    for error in (NoSourceRepo, UnresolvableRef):
        assert issubclass(error, SourceError)
