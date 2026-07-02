"""exception hierarchy for srcverify."""


class SrcverifyError(Exception):
    """base for every error raised by srcverify."""


class RequirementsError(SrcverifyError):
    """a requirements file could not be reduced to exact pins."""

    def __init__(self, line: str, reason: str) -> None:
        super().__init__(f"{reason}: {line!r}")
        self.line = line
        self.reason = reason


class UnpinnedRequirement(RequirementsError):
    """a requirement is not pinned to an exact == version."""


class MalformedRequirement(RequirementsError):
    """a line cannot be parsed as a requirement."""


class UnsupportedRequirementLine(RequirementsError):
    """a line is not a plain pypi requirement (option, path, url)."""


class ConflictingPins(RequirementsError):
    """one name is pinned to two different versions."""


class PypiError(SrcverifyError):
    """base for pypi metadata and download failures."""


class FetchError(PypiError):
    """a network read failed or violated the transport policy."""


class MetadataError(PypiError):
    """a pypi response is not the json shape we require."""


class NoSdist(PypiError):
    """no usable sdist artifact exists for the version."""


class IntegrityError(PypiError):
    """downloaded bytes do not match the declared digest."""


class SdistError(SrcverifyError):
    """base for sdist extraction failures."""


class MalformedArchive(SdistError):
    """not a readable gzip tar, or no single top-level directory."""


class UnsafeArchiveEntry(SdistError):
    """a member escapes the target, is a link, or is a special file."""


class RepoError(SrcverifyError):
    """base for source repository failures."""


class InvalidRepoUrl(RepoError):
    """a repository url failed validation."""


class CloneError(RepoError):
    """git could not clone the repository."""


class RefNotFound(RepoError):
    """the claimed ref does not exist in the repository."""
