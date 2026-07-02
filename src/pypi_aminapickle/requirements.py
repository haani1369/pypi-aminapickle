"""parse a requirements file into exact (name, version) pins."""

from collections.abc import Iterator
from dataclasses import dataclass

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from pypi_aminapickle.errors import (
    ConflictingPins,
    MalformedRequirement,
    UnpinnedRequirement,
    UnsupportedRequirementLine,
)

_VCS_PREFIXES = ("git+", "hg+", "svn+", "bzr+")


@dataclass(frozen=True)
class PinnedRequirement:
    name: str
    version: str


def parse_requirements(text: str) -> list[PinnedRequirement]:
    entries: list[PinnedRequirement] = []
    pinned: dict[str, str] = {}
    for line in _logical_lines(text):
        entry = _parse_line(line)
        seen = pinned.get(entry.name)
        if seen is None:
            pinned[entry.name] = entry.version
            entries.append(entry)
        elif seen != entry.version:
            raise ConflictingPins(
                line, f"{entry.name} pinned to both {seen} and {entry.version}"
            )
    return entries


def load_requirements(path: str) -> list[PinnedRequirement]:
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    return parse_requirements(text)


def _logical_lines(text: str) -> Iterator[str]:
    buffer = ""
    for raw in text.splitlines():
        if raw.endswith("\\"):
            buffer += raw[:-1]
            continue
        line = _strip_comment(buffer + raw).strip()
        buffer = ""
        if line:
            yield line
    tail = _strip_comment(buffer).strip()
    if tail:
        yield tail


def _strip_comment(line: str) -> str:
    quote: str | None = None
    for index, char in enumerate(line):
        if quote is not None:
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char == "#":
            return line[:index]
    return line


def _parse_line(line: str) -> PinnedRequirement:
    if line.startswith("-"):
        raise UnsupportedRequirementLine(line, "option or include line")
    if (
        line.startswith(("./", "../", "/"))
        or "://" in line
        or line.startswith(_VCS_PREFIXES)
    ):
        raise UnsupportedRequirementLine(line, "path or url reference")
    try:
        requirement = Requirement(line)
    except InvalidRequirement as exc:
        raise MalformedRequirement(line, str(exc)) from exc
    if requirement.url is not None:
        raise UnsupportedRequirementLine(line, "url or vcs reference")
    return _pin(line, requirement)


def _pin(line: str, requirement: Requirement) -> PinnedRequirement:
    specifiers = list(requirement.specifier)
    if len(specifiers) != 1:
        raise UnpinnedRequirement(line, "not pinned to an exact version")
    specifier = specifiers[0]
    if specifier.operator != "==":
        raise UnpinnedRequirement(
            line, f"operator {specifier.operator} is not =="
        )
    if "*" in specifier.version:
        raise UnpinnedRequirement(line, "wildcard is not an exact pin")
    try:
        Version(specifier.version)
    except InvalidVersion as exc:
        raise MalformedRequirement(line, str(exc)) from exc
    return PinnedRequirement(
        name=str(canonicalize_name(requirement.name)),
        version=specifier.version,
    )
