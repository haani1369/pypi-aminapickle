"""safely extract an untrusted sdist into a digest tree."""

import functools
import hashlib
import os
import stat
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import PurePath, PurePosixPath

from pypi_aminapickle.errors import MalformedArchive, UnsafeArchiveEntry

_Reader = Callable[[], bytes]


def extract_sdist(sdist_path: str, dest_dir: str) -> str:
    if _detect_format(sdist_path) == "tar":
        top = _extract_tar(sdist_path, dest_dir)
    else:
        top = _extract_zip(sdist_path, dest_dir)
    root = os.path.join(dest_dir, top)
    os.makedirs(root, exist_ok=True)
    return root


def sdist_files(root: str) -> dict[str, str]:
    tree: dict[str, str] = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            full = os.path.join(dirpath, filename)
            key = PurePath(os.path.relpath(full, root)).as_posix()
            tree[key] = _sha256_file(full)
    return tree


def _detect_format(sdist_path: str) -> str:
    try:
        with open(sdist_path, "rb") as handle:
            head = handle.read(2)
    except OSError as exc:
        raise MalformedArchive(f"unreadable sdist: {exc}") from exc
    if head == b"\x1f\x8b":
        return "tar"
    if head == b"PK":
        return "zip"
    raise MalformedArchive("sdist is neither a gzip tar nor a zip")


def _extract_tar(sdist_path: str, dest_dir: str) -> str:
    try:
        with tarfile.open(sdist_path, "r:gz") as archive:
            members = archive.getmembers()
            top = _single_top([(m.name, _tar_kind(m)) for m in members])
            for member in members:
                _place(
                    dest_dir,
                    member.name,
                    _tar_kind(member),
                    functools.partial(_tar_bytes, archive, member),
                )
            return top
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise MalformedArchive(f"unreadable gzip tar: {exc}") from exc


def _extract_zip(sdist_path: str, dest_dir: str) -> str:
    try:
        with zipfile.ZipFile(sdist_path) as archive:
            infos = archive.infolist()
            top = _single_top([(i.filename, _zip_kind(i)) for i in infos])
            for info in infos:
                _place(
                    dest_dir,
                    info.filename,
                    _zip_kind(info),
                    functools.partial(archive.read, info),
                )
            return top
    except (zipfile.BadZipFile, OSError) as exc:
        raise MalformedArchive(f"unreadable zip: {exc}") from exc


def _tar_kind(member: tarfile.TarInfo) -> str:
    if member.issym() or member.islnk():
        return "unsafe"
    if member.isdir():
        return "dir"
    if member.isfile():
        return "file"
    return "unsafe"


def _zip_kind(info: zipfile.ZipInfo) -> str:
    file_type = stat.S_IFMT(info.external_attr >> 16)
    if file_type == stat.S_IFLNK:
        return "unsafe"
    if info.is_dir() or file_type == stat.S_IFDIR:
        return "dir"
    if file_type in (stat.S_IFREG, 0):
        return "file"
    return "unsafe"


def _tar_bytes(archive: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    extracted = archive.extractfile(member)
    return extracted.read() if extracted is not None else b""


def _single_top(entries: list[tuple[str, str]]) -> str:
    tops = set()
    for name, kind in entries:
        _check_entry(name, kind)
        tops.add(PurePosixPath(name).parts[0])
    if len(tops) != 1:
        raise MalformedArchive(
            f"expected one top-level directory, found {sorted(tops)}"
        )
    return next(iter(tops))


def _check_entry(name: str, kind: str) -> None:
    if kind == "unsafe":
        raise UnsafeArchiveEntry(f"link or special member: {name!r}")
    if name.startswith("/") or os.path.isabs(name):
        raise UnsafeArchiveEntry(f"absolute member: {name!r}")
    parts = PurePosixPath(name).parts
    if not parts or ".." in parts:
        raise UnsafeArchiveEntry(f"unsafe member path: {name!r}")


def _place(dest_dir: str, name: str, kind: str, read: _Reader) -> None:
    parts = PurePosixPath(name).parts
    target = os.path.join(dest_dir, *parts)
    real_dest = os.path.realpath(dest_dir)
    if os.path.commonpath([real_dest, os.path.realpath(target)]) != real_dest:
        raise UnsafeArchiveEntry(f"member escapes dest: {name!r}")
    if kind == "dir":
        os.makedirs(target, exist_ok=True)
        return
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as handle:
        handle.write(read())


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
