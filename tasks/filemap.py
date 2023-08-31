"""
    tasks.filemap
    ~~~~~~~~~~~~~

    tests/filename_map.yml validity checks
"""
import pathlib
import re

import yaml
from invoke import task  # pylint: disable=3rd-party-module-not-gated

from tasks import utils

CODE_DIR = pathlib.Path(__file__).resolve().parent.parent
FILENAME_MAP_PATH = CODE_DIR / "tests" / "filename_map.yml"


def _match_to_test_file(match):
    tests_path = CODE_DIR / "tests"
    parts = match.split(".")
    parts[-1] += ".py"
    return tests_path.joinpath(*parts).relative_to(CODE_DIR)


def _check_matches(rule, matches):
    errors = 0
    for match in matches:
        filematch = _match_to_test_file(match)
        if not filematch.exists():
            utils.error(
                "The match '{}' for rule '{}' points to a non existing test module"
                " path: {}",
                match,
                rule,
                filematch,
            )
            errors += 1
    return errors


@task
def check(ctx):
    exitcode = 0
    excludes = ("tasks/", "templates/", ".nox/")
    full_filelist = [path.relative_to(CODE_DIR) for path in CODE_DIR.rglob("*.py")]
    filelist = [
        str(path) for path in full_filelist if not str(path).startswith(excludes)
    ]
    filename_map = yaml.safe_load(FILENAME_MAP_PATH.read_text())
    checked = set()
    for rule, matches in filename_map.items():
        if rule == "*":
            exitcode += _check_matches(rule, matches)
        elif "|" in rule:
            # This is regex
            for filepath in filelist:
                if re.match(rule, filepath):
                    # Found at least one match, stop looking
                    break
            else:
                utils.error(
                    "Could not find a matching file in the salt repo for the rule '{}'",
                    rule,
                )
                exitcode += 1
                continue
            exitcode += _check_matches(rule, matches)
        elif "*" in rule or "\\" in rule:
            # Glob matching
            process_matches = True
            for filerule in CODE_DIR.glob(rule):
                if not filerule.exists():
                    utils.error(
                        "The rule '{}' points to a non existing path: {}",
                        rule,
                        filerule,
                    )
                    exitcode += 1
                    process_matches = False
            if process_matches:
                exitcode += _check_matches(rule, matches)
        else:
            # Direct file paths as rules
            filerule = pathlib.Path(rule)
            if not filerule.exists():
                utils.error(
                    "The rule '{}' points to a non existing path: {}", rule, filerule
                )
                exitcode += 1
                continue
            exitcode += _check_matches(rule, matches)
    if exitcode:
        utils.error("Found {} errors", exitcode)
    utils.exit_invoke(exitcode)
