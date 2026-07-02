import pytest

from pypi_aminapickle.errors import (
    NoSourceRepo,
    PypiAminapickleError,
    SourceError,
    UnresolvableRef,
)
from pypi_aminapickle.pypi import Metadata
from pypi_aminapickle.source import (
    candidate_refs,
    resolve_ref,
    resolve_repo_url,
)


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


def test_resolve_ref_exact_candidate() -> None:
    assert resolve_ref("pkg", "1.0.0", ["main", "v1.0.0"]) == "v1.0.0"


def test_resolve_ref_candidate_order_wins() -> None:
    # v{version} is tried before {version}; both exist
    assert resolve_ref("pkg", "1.0.0", ["1.0.0", "v1.0.0"]) == "v1.0.0"


def test_resolve_ref_zero_padded_calver() -> None:
    assert resolve_ref("certifi", "2024.2.2", ["main", "2024.02.02"]) == (
        "2024.02.02"
    )


def test_resolve_ref_trailing_zero_with_prefix() -> None:
    assert resolve_ref("pkg", "1.2.0", ["v1.2"]) == "v1.2"


def test_resolve_ref_none_matches() -> None:
    with pytest.raises(UnresolvableRef):
        resolve_ref("pkg", "1.0.0", ["main", "dev"])


def test_error_hierarchy() -> None:
    assert issubclass(SourceError, PypiAminapickleError)
    for error in (NoSourceRepo, UnresolvableRef):
        assert issubclass(error, SourceError)
