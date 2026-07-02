import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from pypi_aminapickle.errors import (
    MalformedArchive,
    PypiAminapickleError,
    SdistError,
    UnsafeArchiveEntry,
)
from pypi_aminapickle.sdist import extract_sdist, sdist_files


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def add_file(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.type = tarfile.REGTYPE
    info.size = len(data)
    info.mode = 0o644
    info.mtime = 0
    tar.addfile(info, io.BytesIO(data))


def add_dir(tar: tarfile.TarFile, name: str) -> None:
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE
    info.mode = 0o755
    info.mtime = 0
    tar.addfile(info)


def add_special(
    tar: tarfile.TarFile,
    name: str,
    kind: bytes,
    linkname: str = "",
) -> None:
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = linkname
    info.mode = 0o644
    info.mtime = 0
    tar.addfile(info)


def make_archive(path: Path, members: list[tuple[str, bytes]]) -> str:
    with tarfile.open(str(path), "w:gz") as tar:
        for name, data in members:
            add_file(tar, name, data)
    return str(path)


def fresh_dir(tmp_path: Path, name: str) -> str:
    dest = tmp_path / name
    dest.mkdir()
    return str(dest)


def test_normal_archive(tmp_path: Path) -> None:
    pkg_info = b"Metadata-Version: 2.1\nName: pkg\n"
    init = b"__version__ = '1.0'\n"
    archive = make_archive(
        tmp_path / "pkg-1.0.tar.gz",
        [
            ("pkg-1.0/PKG-INFO", pkg_info),
            ("pkg-1.0/src/pkg/__init__.py", init),
        ],
    )
    dest = fresh_dir(tmp_path, "dest")
    root = extract_sdist(archive, dest)
    root_path = Path(root)
    assert root_path.name == "pkg-1.0"
    assert root_path.is_dir()
    assert root_path.parent == Path(dest)
    assert sdist_files(root) == {
        "PKG-INFO": sha256_hex(pkg_info),
        "src/pkg/__init__.py": sha256_hex(init),
    }


def test_absolute_path_member(tmp_path: Path) -> None:
    with tarfile.open(str(tmp_path / "a.tar.gz"), "w:gz") as tar:
        add_file(tar, "pkg-1.0/PKG-INFO", b"ok")
        add_file(tar, "/etc/passwd", b"root")
    dest = fresh_dir(tmp_path, "dest")
    with pytest.raises(UnsafeArchiveEntry):
        extract_sdist(str(tmp_path / "a.tar.gz"), dest)


def test_dotdot_component_member(tmp_path: Path) -> None:
    with tarfile.open(str(tmp_path / "a.tar.gz"), "w:gz") as tar:
        add_file(tar, "pkg-1.0/PKG-INFO", b"ok")
        add_file(tar, "pkg-1.0/../evil.py", b"evil")
    dest = fresh_dir(tmp_path, "dest")
    with pytest.raises(UnsafeArchiveEntry):
        extract_sdist(str(tmp_path / "a.tar.gz"), dest)


def test_symlink_member(tmp_path: Path) -> None:
    with tarfile.open(str(tmp_path / "a.tar.gz"), "w:gz") as tar:
        add_file(tar, "pkg-1.0/PKG-INFO", b"ok")
        add_special(
            tar, "pkg-1.0/link", tarfile.SYMTYPE, linkname="/etc/passwd"
        )
    dest = fresh_dir(tmp_path, "dest")
    with pytest.raises(UnsafeArchiveEntry):
        extract_sdist(str(tmp_path / "a.tar.gz"), dest)


def test_hardlink_member(tmp_path: Path) -> None:
    with tarfile.open(str(tmp_path / "a.tar.gz"), "w:gz") as tar:
        add_file(tar, "pkg-1.0/PKG-INFO", b"ok")
        add_special(
            tar, "pkg-1.0/hard", tarfile.LNKTYPE, linkname="pkg-1.0/PKG-INFO"
        )
    dest = fresh_dir(tmp_path, "dest")
    with pytest.raises(UnsafeArchiveEntry):
        extract_sdist(str(tmp_path / "a.tar.gz"), dest)


def test_fifo_member(tmp_path: Path) -> None:
    with tarfile.open(str(tmp_path / "a.tar.gz"), "w:gz") as tar:
        add_file(tar, "pkg-1.0/PKG-INFO", b"ok")
        add_special(tar, "pkg-1.0/pipe", tarfile.FIFOTYPE)
    dest = fresh_dir(tmp_path, "dest")
    with pytest.raises(UnsafeArchiveEntry):
        extract_sdist(str(tmp_path / "a.tar.gz"), dest)


def test_non_tar_file(tmp_path: Path) -> None:
    path = tmp_path / "a.tar.gz"
    path.write_bytes(b"not a tar")
    dest = fresh_dir(tmp_path, "dest")
    with pytest.raises(MalformedArchive):
        extract_sdist(str(path), dest)


def test_two_top_level_dirs(tmp_path: Path) -> None:
    archive = make_archive(
        tmp_path / "a.tar.gz",
        [("a-1.0/x", b"x"), ("b-2.0/y", b"y")],
    )
    dest = fresh_dir(tmp_path, "dest")
    with pytest.raises(MalformedArchive):
        extract_sdist(archive, dest)


def test_empty_archive(tmp_path: Path) -> None:
    with tarfile.open(str(tmp_path / "a.tar.gz"), "w:gz"):
        pass
    dest = fresh_dir(tmp_path, "dest")
    with pytest.raises(MalformedArchive):
        extract_sdist(str(tmp_path / "a.tar.gz"), dest)


def test_error_hierarchy() -> None:
    assert issubclass(SdistError, PypiAminapickleError)
    for error in (MalformedArchive, UnsafeArchiveEntry):
        assert issubclass(error, SdistError)


def test_rejected_archive_stays_contained(tmp_path: Path) -> None:
    box = tmp_path / "box"
    box.mkdir()
    dest = box / "dest"
    dest.mkdir()
    sentinel = box / "sentinel"
    sentinel.write_text("keep")
    before = set(p.name for p in box.iterdir())
    with tarfile.open(str(tmp_path / "a.tar.gz"), "w:gz") as tar:
        add_file(tar, "pkg-1.0/PKG-INFO", b"ok")
        add_file(tar, "pkg-1.0/../../escape.py", b"escape")
    with pytest.raises(UnsafeArchiveEntry):
        extract_sdist(str(tmp_path / "a.tar.gz"), str(dest))
    after = set(p.name for p in box.iterdir())
    assert after == before
    assert not (box / "escape.py").exists()
    assert not (tmp_path / "escape.py").exists()
