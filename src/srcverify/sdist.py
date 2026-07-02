"""safely extract an untrusted sdist into a digest tree."""

import hashlib
import os
import tarfile
from pathlib import PurePath, PurePosixPath

from srcverify.errors import MalformedArchive, UnsafeArchiveEntry


def extract_sdist(sdist_path: str, dest_dir: str) -> str:
    try:
        with tarfile.open(sdist_path, "r:gz") as archive:
            members = archive.getmembers()
            top = _single_top(members)
            for member in members:
                _extract_member(archive, member, dest_dir)
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise MalformedArchive(f"unreadable gzip tar: {exc}") from exc
    root = os.path.join(dest_dir, top)
    os.makedirs(root, exist_ok=True)
    return root


def _single_top(members: list[tarfile.TarInfo]) -> str:
    tops = set()
    for member in members:
        _validate_member(member)
        tops.add(PurePosixPath(member.name).parts[0])
    if len(tops) != 1:
        raise MalformedArchive(
            f"expected one top-level directory, found {sorted(tops)}"
        )
    return next(iter(tops))


def sdist_files(root: str) -> dict[str, str]:
    tree: dict[str, str] = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            full = os.path.join(dirpath, filename)
            key = PurePath(os.path.relpath(full, root)).as_posix()
            tree[key] = _sha256_file(full)
    return tree


def _validate_member(member: tarfile.TarInfo) -> None:
    name = member.name
    if member.issym() or member.islnk():
        raise UnsafeArchiveEntry(f"link member: {name!r}")
    if not (member.isfile() or member.isdir()):
        raise UnsafeArchiveEntry(f"special member: {name!r}")
    if name.startswith("/") or os.path.isabs(name):
        raise UnsafeArchiveEntry(f"absolute member: {name!r}")
    parts = PurePosixPath(name).parts
    if not parts or ".." in parts:
        raise UnsafeArchiveEntry(f"unsafe member path: {name!r}")


def _extract_member(
    archive: tarfile.TarFile, member: tarfile.TarInfo, dest_dir: str
) -> None:
    parts = PurePosixPath(member.name).parts
    target = os.path.join(dest_dir, *parts)
    real_dest = os.path.realpath(dest_dir)
    real_target = os.path.realpath(target)
    if os.path.commonpath([real_dest, real_target]) != real_dest:
        raise UnsafeArchiveEntry(f"member escapes dest: {member.name!r}")
    if member.isdir():
        os.makedirs(target, exist_ok=True)
        return
    os.makedirs(os.path.dirname(target), exist_ok=True)
    extracted = archive.extractfile(member)
    data = extracted.read() if extracted is not None else b""
    with open(target, "wb") as handle:
        handle.write(data)


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
