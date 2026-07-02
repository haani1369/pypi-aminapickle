"""resolve the source repo url and claimed ref from metadata."""

from urllib.parse import urlparse

from pypi_aminapickle.errors import NoSourceRepo, UnresolvableRef
from pypi_aminapickle.pypi import Metadata

_HOSTS = frozenset(
    {"github.com", "gitlab.com", "bitbucket.org", "codeberg.org"}
)

_PREFERRED_LABELS = frozenset(
    {"source", "sourcecode", "repository", "code", "github", "gitlab"}
)


def resolve_repo_url(metadata: Metadata) -> str:
    items = list(metadata.project_urls.items())
    preferred = [
        value
        for label, value in items
        if _normalize_label(label) in _PREFERRED_LABELS
    ]
    for value in preferred + [value for _, value in items]:
        repo = _as_repo(value)
        if repo is not None:
            return repo
    raise NoSourceRepo("no recognized repository url in metadata")


def candidate_refs(name: str, version: str) -> list[str]:
    return [
        f"v{version}",
        version,
        f"release-{version}",
        f"{name}-{version}",
    ]


def select_ref(candidates: list[str], available: list[str]) -> str:
    known = set(available)
    for candidate in candidates:
        if candidate in known:
            return candidate
    raise UnresolvableRef(f"no candidate tag among {candidates}")


def _normalize_label(label: str) -> str:
    return "".join(char for char in label.lower() if char.isalnum())


def _as_repo(value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.scheme != "https":
        return None
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[len("www.") :]
    if host not in _HOSTS:
        return None
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 2:
        return None
    owner, repo = segments[0], segments[1]
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]
    if not repo:
        return None
    return f"https://{host}/{owner}/{repo}"
