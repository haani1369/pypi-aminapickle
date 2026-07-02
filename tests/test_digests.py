import hashlib
from pathlib import Path

from pypi_aminapickle.digests import file_digest

# same options, but reformatted the way setuptools rewrites setup.cfg:
# 4-space indent -> tab, comments dropped, and an [egg_info] section
# appended.
REPO_CFG = b"""[metadata]
name = demo
# a comment about classifiers
classifiers =
    A
    B

[options]
python_requires = >= 3.7
"""

SDIST_CFG = b"""[metadata]
name = demo
classifiers =
\tA
\tB

[options]
python_requires = >= 3.7

[egg_info]
tag_build =
tag_date = 0
"""

CHANGED_CFG = b"""[metadata]
name = demo
classifiers =
    A
    B

[options]
python_requires = >= 3.8
"""


def write(tmp_path: Path, name: str, data: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def test_setup_cfg_reformatting_matches(tmp_path: Path) -> None:
    repo = write(tmp_path, "repo_setup.cfg", REPO_CFG)
    sdist = write(tmp_path, "sdist_setup.cfg", SDIST_CFG)
    assert file_digest("setup.cfg", repo) == file_digest("setup.cfg", sdist)


def test_setup_cfg_real_change_differs(tmp_path: Path) -> None:
    repo = write(tmp_path, "a_setup.cfg", REPO_CFG)
    changed = write(tmp_path, "b_setup.cfg", CHANGED_CFG)
    assert file_digest("setup.cfg", repo) != file_digest("setup.cfg", changed)


def test_nested_setup_cfg_normalized(tmp_path: Path) -> None:
    repo = write(tmp_path, "r.cfg", REPO_CFG)
    sdist = write(tmp_path, "s.cfg", SDIST_CFG)
    assert file_digest("sub/setup.cfg", repo) == file_digest(
        "sub/setup.cfg", sdist
    )


def test_non_setup_cfg_is_plain_sha256(tmp_path: Path) -> None:
    data = b"print('hello')\n"
    path = write(tmp_path, "mod.py", data)
    assert file_digest("mod.py", path) == hashlib.sha256(data).hexdigest()


def test_unparseable_setup_cfg_falls_back_to_bytes(tmp_path: Path) -> None:
    junk = b"this is not ini at all\n= broken\n"
    path = write(tmp_path, "j_setup.cfg", junk)
    assert file_digest("setup.cfg", path) == hashlib.sha256(junk).hexdigest()
