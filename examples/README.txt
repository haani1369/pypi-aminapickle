examples


this directory is a guided tour of what pypi-aminapickle reports,
using real, currently-published packages. run it with:

    pypi-aminapickle examples/requirements.txt

the results below are representative; they reflect live pypi and
github state and can shift as packages publish new releases or move
their repositories.


representative output

    [MATCH] id==1.5.0 -> https://github.com/di/id@1f665ce45ab0...
    [MATCH] certifi==2024.2.2 -> https://github.com/certifi/python-certifi@2024.02.02
    [MISMATCH] distlib==0.3.8 -> https://github.com/pypa/distlib@0.3.8 (4 differing files)
        extra: tests/keys/.gpg-v21-migrated
        extra: tests/keys/private-keys-v1.d/89643D011E...key
        extra: tests/keys/private-keys-v1.d/8BE462CC60...key
        extra: tests/keys/random_seed
    [MISMATCH] pyyaml==6.0.2 -> https://github.com/yaml/pyyaml@6.0.2 (1 differing file)
        extra: packaging/__pycache__/_pyyaml_pep517.cpython-312.pyc
    [UNVERIFIED] pytz==2024.1 (no recognized repository url in metadata)
    [UNVERIFIED] docutils==0.21.2 (link or special member: '.../html4css1.css')
    6 packages: 2 match, 2 mismatch, 2 unverified

    the process exits non-zero because not every package matched.


what each case shows

    id==1.5.0
        the strongest path. the release carries a pep 740 provenance
        attestation, so the exact commit the artifact was built from
        is read from the signed statement. before it is trusted, the
        dsse signature is verified under the certificate, the
        certificate is checked to chain to the pinned sigstore fulcio
        roots, and its identity is confirmed to belong to the source
        repo. the sdist is then compared against that exact commit
        and matches.

    certifi==2024.2.2
        the repo tags this calendar-versioned release "2024.02.02"
        while the pin is "2024.2.2". an exact tag lookup would miss
        it; version-normalized matching finds it and the contents
        match.

    distlib==0.3.8
        a real divergence: the published sdist ships files that do
        not exist in the tagged source, including gpg private test
        keys under tests/keys/. these are reported as extra files.
        the tool draws no conclusion about intent; it reports that
        the artifact carries content its public source does not.

    pyyaml==6.0.2
        another divergence: the sdist ships a compiled python
        bytecode file (a .pyc under __pycache__) that is not part of
        the source. benign build noise like a reformatted setup.cfg
        is normalized away, so this genuine extra stands out.

    pytz==2024.1
        the project's metadata lists no repository on a recognized
        host, so the source link cannot be established. rather than
        pass or guess, the tool reports unverified with the reason.

    docutils==0.21.2
        the sdist contains a symlink. extraction is hardened against
        untrusted archives and refuses to follow or materialize
        links, so the package is reported unverified with that
        reason rather than risking an unsafe extraction.


the three verdicts

    match       every shipped file is present in the repo, unchanged.
    mismatch    the sdist adds or alters files relative to the repo.
    unverified  the link could not be safely established (no repo,
                an unresolvable ref, an unsafe archive, and so on).

only match answers the tool's question with "yes". see the top-level
README.txt for install and usage, and docs/ for the design.
