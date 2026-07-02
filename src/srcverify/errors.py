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
