"""command-line entry point."""

import argparse
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TextIO

from pypi_aminapickle.errors import RequirementsError
from pypi_aminapickle.report import (
    PackageResult,
    all_match,
    render_json,
    render_text,
)
from pypi_aminapickle.requirements import PinnedRequirement, load_requirements
from pypi_aminapickle.verify import verify_package

_Verifier = Callable[[PinnedRequirement], PackageResult]


def run(
    argv: list[str],
    *,
    verify: _Verifier,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    args = _parse(argv)
    try:
        requirements = load_requirements(args.requirements)
    except RequirementsError as exc:
        print(str(exc), file=stderr)
        return 2
    except OSError as exc:
        print(f"cannot read {args.requirements}: {exc}", file=stderr)
        return 2
    results = _verify_all(requirements, verify, args.jobs)
    text = render_json(results) if args.json else render_text(results)
    print(text, file=stdout)
    return 0 if all_match(results) else 1


def _verify_all(
    requirements: list[PinnedRequirement], verify: _Verifier, jobs: int
) -> list[PackageResult]:
    workers = min(jobs, len(requirements))
    if workers <= 1:
        return [verify(req) for req in requirements]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(verify, requirements))


def main(argv: list[str] | None = None) -> int:
    return run(
        sys.argv[1:] if argv is None else argv,
        verify=verify_package,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pypi-aminapickle",
        description="verify that pypi sdists match their claimed source",
    )
    parser.add_argument(
        "requirements", help="path to a pinned requirements.txt"
    )
    parser.add_argument(
        "--json", action="store_true", help="emit json instead of text"
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=8,
        help="max packages to verify in parallel (default 8)",
    )
    return parser.parse_args(argv)
