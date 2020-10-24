#!/usr/bin/env python
# pylint: skip-file

import pathlib
import re
import sys

CODE_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS_PATH = CODE_ROOT / "doc"
TESTS_INTEGRATION_FILES_PATH = CODE_ROOT / "tests" / "integration" / "files"
CHANGELOG_ENTRIES_PATH = CODE_ROOT / "changelog"
CHANGELOG_LIKE_RE = re.compile(r"([\d]+)\.([a-z]+)$")
CHANGELOG_EXTENSIONS = ("removed", "deprecated", "changed", "fixed", "added")
CHANGELOG_ENTRY_RE = re.compile(r"[\d]+\.({})$".format("|".join(CHANGELOG_EXTENSIONS)))


def check_changelog_entries(files):

    exitcode = 0
    for entry in files:
        path = pathlib.Path(entry).resolve()
        # Does it look like a changelog entry
        if CHANGELOG_LIKE_RE.match(path.name) and not CHANGELOG_ENTRY_RE.match(
            path.name
        ):
            try:
                # Is this under doc/
                path.relative_to(DOCS_PATH)
                # Yes, carry on
                continue
            except ValueError:
                # No, resume the check
                pass
            try:
                # Is this under tests/integration/files
                path.relative_to(TESTS_INTEGRATION_FILES_PATH)
                # Yes, carry on
                continue
            except ValueError:
                # No, resume the check
                pass
            print(
                "The changelog entry '{}' should have one of the following extensions: {}.".format(
                    path.relative_to(CODE_ROOT),
                    ", ".join(repr(ext) for ext in CHANGELOG_EXTENSIONS),
                ),
                file=sys.stderr,
                flush=True,
            )
            exitcode = 1
            continue
        # Is it a changelog entry
        if not CHANGELOG_ENTRY_RE.match(path.name):
            # No? Carry on
            continue
        # Is the changelog entry in the right path?
        try:
            path.relative_to(CHANGELOG_ENTRIES_PATH)
        except ValueError:
            exitcode = 1
            print(
                "The changelog entry '{}' should be placed under '{}/', not '{}'".format(
                    path.name,
                    CHANGELOG_ENTRIES_PATH.relative_to(CODE_ROOT),
                    path.relative_to(CODE_ROOT).parent,
                ),
                file=sys.stderr,
                flush=True,
            )
    sys.exit(exitcode)


if __name__ == "__main__":
    check_changelog_entries(sys.argv[1:])
