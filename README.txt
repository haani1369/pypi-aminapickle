pypi-aminapickle


most dependency scanners check a package against a list of known
cves. none of them check whether the code you are installing is the
code the maintainer actually published on github. pypi-aminapickle
does exactly that. given a pinned requirements file, it answers one
question per package: does the sdist published on pypi match the
source in its linked git repository at the release it claims to come
from, yes or no.

it downloads and compares file contents only. it never builds,
imports, or runs any fetched code, and it makes no judgment about
whether a package is safe; it reports whether the artifact matches
its public source.


why it matters

    a normal install trusts pypi to serve the code the maintainer
    published, but never checks that against the public source. most
    of the time that trust holds; when it doesn't, a compromised
    account or a tampered upload can ship code the tagged source never
    had, and nothing in the usual flow would notice.

    that is the one gap this closes, and nothing more. it does not
    prove a package is safe, replace a vulnerability scanner, or see
    past the sdist, and plenty of packages it simply cannot verify. it
    is a small, best-effort check, and "i can't verify this" is treated
    as an honest answer rather than a failure. mostly it is an excuse
    to take an idea that is usually hand-waved and make it concrete.


how it works

    for each pinned package it fetches the pypi metadata, downloads
    and safely unpacks the sdist, finds the source point, clones the
    repo there, and diffs the two file trees.

    to find the source point it prefers a pep 740 provenance
    attestation: it binds the attestation to the downloaded sdist by
    digest, verifies the dsse signature, that the certificate chains
    to the pinned sigstore fulcio roots, and that its identity is the
    source repo, then clones the exact commit. with no attestation it
    resolves the repo from the project's urls and matches the version
    to an existing tag.

    build noise that is not real divergence (PKG-INFO, *.egg-info, a
    setuptools-rewritten setup.cfg) is normalized away, so genuine
    differences stand out.


install

    python -m venv .venv
    . .venv/bin/activate
    pip install --require-hashes -r requirements-dev.lock
    pip install --no-deps -e .


usage

    pypi-aminapickle requirements.txt          human-readable report
    pypi-aminapickle --json requirements.txt   machine-readable report
    pypi-aminapickle --jobs 16 requirements.txt   set the parallelism

    every package must be pinned to an exact version (name==version);
    an unpinned entry is a hard error. each package is reported as one
    of three verdicts, and only match answers the question with "yes":

        match       every shipped file is present in the repo,
                    unchanged.
        mismatch    the sdist adds or alters files relative to the
                    repo.
        unverified  the link could not be established (no repo, an
                    unresolvable tag, a failed download, and so on).

    the process exits 0 when every package matched, 1 when any did
    not, and 2 on a bad requirements file, so it works as a ci gate.


example

    examples/requirements.txt is a tour over real packages. running
    it (commit and long paths abbreviated for width):

        $ pypi-aminapickle examples/requirements.txt
        [MATCH] id==1.5.0 -> https://github.com/di/id@1f665ce4...
        [MATCH] certifi==2024.2.2 -> .../python-certifi@2024.02.02
        [MISMATCH] distlib==0.3.8 -> .../distlib@0.3.8 (4 differing files)
            extra: tests/keys/.gpg-v21-migrated
            extra: tests/keys/private-keys-v1.d/89643D01...key
            extra: tests/keys/private-keys-v1.d/8BE462CC...key
            extra: tests/keys/random_seed
        [MISMATCH] pyyaml==6.0.2 -> .../pyyaml@6.0.2 (1 differing file)
            extra: packaging/__pycache__/_pyyaml_pep517.cpython-312.pyc
        [UNVERIFIED] pytz==2024.1 (no recognized repository url in metadata)
        5 packages: 2 match, 2 mismatch, 1 unverified

    id verifies through a signed attestation and matches its exact
    build commit. certifi's calver tag "2024.02.02" is resolved for
    the pin "2024.2.2". distlib's sdist ships gpg private test keys
    absent from its source, and pyyaml's ships a compiled .pyc; both
    are reported. pytz lists no repository on a recognized host, so
    the link cannot be established. see examples/README.txt for the
    walkthrough.


develop

    the design lives in docs/ (start with docs/architecture.txt); each
    component has a spec written before its tests and implementation.
    the checks, also run in ci:

        black --check src tests
        ruff check src tests
        mypy
        pytest                 offline suite
        pytest -m integration  live pypi + github suite
