srcverify


srcverify checks whether the sdist published on pypi for a pinned
package matches the source in its linked git repository at the release
it claims to correspond to. it answers one question per package: does
the artifact you are about to install match its public source, yes or
no. it downloads and compares file contents only; it never builds,
imports, or runs any fetched code, and it makes no judgment about
whether a package is safe.


install

    python -m venv .venv
    . .venv/bin/activate
    pip install --require-hashes -r requirements-dev.lock
    pip install --no-deps -e .


use

    srcverify requirements.txt          human-readable report
    srcverify --json requirements.txt   machine-readable report

the requirements file must pin every package to an exact version
(name==version); an unpinned entry is a hard error. the process exits
0 when every package matches, 1 when any does not, and 2 on a bad
requirements file.

to find the source point, srcverify prefers a pep 740 provenance
attestation when the release has one: it binds the attestation to the
downloaded sdist by digest and clones the exact commit it names. when
there is no attestation it falls back to resolving the repo from the
package's project urls and matching the version to an existing tag.

each package is reported as one of:

    match        every shipped file is present in the repo, unchanged.
    mismatch     the sdist adds or alters files relative to the repo.
    unverified   the link could not be established (no repo url, an
                 unresolvable tag, a failed download, and so on).


develop

    the design lives in docs/. each component has a spec written before
    its tests and implementation. run the checks with:

        black --check src tests
        ruff check src tests
        mypy
        pytest                 offline suite
        pytest -m integration  live pypi + github suite

see docs/architecture.txt for the component map and docs/ci.txt for
the gate.
