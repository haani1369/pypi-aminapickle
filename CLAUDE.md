these are general guidelines for any code, script, design, or
documentation written in this repository. follow them exactly. if
there is ambiguity in scope at any point, stop and ask for
clarification.

this repository holds a supply-chain integrity checker for pypi
packages. given a requirements file, it verifies that the sdist
published on pypi actually matches the source at the git tag/commit
it claims to be built from, and reports any mismatch.

    * any work done at any point must be its own commit.
    * do not make "polluted" commits that touch unrelated parts of
      the code. split those into separate commits.
    * do not build abstractions or add features that were not asked
      for.
    * there must not be any dead code.
    * minimize comments. make code clear through functions, naming,
      and control flow.
    * do not touch code you didn't write.
    * always be as concise as possible.
    * do not use .md files. use plain .txt files.
    * write doc prose in lowercase, titles included. use an extra
      blank line instead of dashes/equals to mark a section.
    * stick to 80 columns, 4-space indentation, no tabs.

workflow:

    1. write a design/spec doc first (docs/<component>.txt).
    2. write tests against that spec only.
    3. implement against the tests.

if a prior step turns out incomplete, stop, fix that step, then
redo the later ones. prefer a fresh agent per step.

the project

most dependency scanners check a package against a list of known
cves. none of them check whether the code you're installing is the
code the maintainer actually published on github. a compromised or
malicious pypi upload can silently diverge from the tagged source
it claims to correspond to, and nothing in a normal pip install
flow would ever catch that.

this tool closes that specific gap. given a pinned requirements
file, it independently rebuilds the link between "what's on pypi"
and "what's in the linked source repo at the claimed release
point", and flags any package where that link is missing, broken,
or contradicted by the actual file contents. it answers one
question per package: does the thing i'm about to install match
the public source it claims to come from, yes or no.

it is a verification tool, not a build tool and not a policy
engine. it makes no judgment about whether a package is safe; it
only reports whether its published artifact matches its claimed
source.

scope

    * input: a requirements.txt (pinned versions only; unpinned
      entries are a hard error).
    * for each package: fetch its pypi json metadata, download the
      published sdist, resolve the source repo url and the tag/
      commit the release claims to correspond to, clone at that
      ref, and diff the sdist contents against the repo contents.
    * a mismatch (extra files, altered files, missing repo link,
      unresolvable ref) is reported, not silently skipped.
    * output: a report, one verdict per package, human-readable and
      machine-readable (json).

non-goals

    * this does not attempt bit-for-bit reproducible wheel builds.
      build nondeterminism (timestamps, compiler versions, path
      embedding) makes that a different, much larger project.
      sdist-vs-source-repo content comparison only.
    * no wheel building, no compiling, no execution of any package
      code at any point. never import or run fetched source.
    * no persistent daemon, no scheduled scanning, no database. one
      invocation, one report.
    * no support for private/internal package indexes.

coding practices — enforced strictly, no exceptions

    * python, type-hinted throughout. no untyped function
      signatures. mypy --strict passes cleanly at all times.
    * no bare `except:`. catch specific exceptions only. every
      caught exception is either handled meaningfully or re-raised;
      never silently swallowed.
    * no `eval`, `exec`, `pickle` on untrusted data, or shelling out
      to unsanitized input.
    * all external input (pypi responses, sdist contents, repo
      contents) is treated as untrusted. never assume well-formed.
    * dependencies pinned exactly, in a lockfile, checked in.
    * every public function has a test. tests run offline against
      recorded fixtures, not live network calls, except for an
      explicitly separate integration suite.
    * formatting and linting (black, ruff) enforced in ci; no
      unformatted or lint-failing commit lands.
    * fetched archives and cloned repos are extracted only into a
      throwaway temp directory, cleaned up on every exit path,
      including on exception.
