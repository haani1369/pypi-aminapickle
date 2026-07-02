"""command-line entry point."""

import argparse
import sys
from collections.abc import Callable
from typing import TextIO

from srcverify.errors import RequirementsError
from srcverify.report import PackageResult, all_match, render_json, render_text
from srcverify.requirements import PinnedRequirement, load_requirements
from srcverify.verify import verify_package

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
    results = [verify(req) for req in requirements]
    text = render_json(results) if args.json else render_text(results)
    print(text, file=stdout)
    return 0 if all_match(results) else 1


def main(argv: list[str] | None = None) -> int:
    return run(
        sys.argv[1:] if argv is None else argv,
        verify=verify_package,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="srcverify",
        description="verify that pypi sdists match their claimed source",
    )
    parser.add_argument(
        "requirements", help="path to a pinned requirements.txt"
    )
    parser.add_argument(
        "--json", action="store_true", help="emit json instead of text"
    )
    return parser.parse_args(argv)
