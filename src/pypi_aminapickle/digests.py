"""content digests, with normalization for build-rewritten files."""

import configparser
import hashlib
import json
import os


def file_digest(relpath: str, path: str) -> str:
    if os.path.basename(relpath) == "setup.cfg":
        with open(path, "rb") as handle:
            return _sha256(_canonical_setup_cfg(handle.read()))
    return _sha256_stream(path)


def _canonical_setup_cfg(raw: bytes) -> bytes:
    parser = configparser.RawConfigParser()
    try:
        parser.read_string(raw.decode("utf-8"))
    except (configparser.Error, UnicodeDecodeError):
        return raw
    data = {
        section: dict(parser.items(section))
        for section in parser.sections()
        if section != "egg_info"
    }
    return json.dumps(data, sort_keys=True).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_stream(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
