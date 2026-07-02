import os

import pytest

from pypi_aminapickle.workspace import workspace


def test_yields_existing_directory_removed_after() -> None:
    with workspace() as path:
        assert os.path.isdir(path)
        captured = path
    assert not os.path.exists(captured)


def test_directory_removed_on_exception() -> None:
    captured = ""
    with pytest.raises(ValueError, match="boom"), workspace() as path:
        captured = path
        assert os.path.isdir(path)
        raise ValueError("boom")
    assert captured
    assert not os.path.exists(captured)
