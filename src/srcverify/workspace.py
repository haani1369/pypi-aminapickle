"""a throwaway temp directory cleaned up on every exit path."""

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def workspace() -> Iterator[str]:
    path = tempfile.mkdtemp(prefix="srcverify-")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
