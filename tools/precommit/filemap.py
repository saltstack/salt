"""
`tests/filename_map.yml` validity checks
"""

import pathlib
import re

import yaml
from ptscripts import Context, command_group

import tools.utils

FILENAME_MAP_PATH = tools.utils.REPO_ROOT / "tests" / "filename_map.yml"

cgroup = command_group(name="filemap", help=__doc__, parent="pre-commit")


def _match_to_test_file(match: str) -> pathlib.Path:
    tests_path = tools.utils.REPO_ROOT / "tests"
    parts = match.split(".")
    parts[-1] += ".py"
    return tests_path.joinpath(*parts).relative_to(tools.utils.REPO_ROOT)


def _check_matches(ctx: Context, rule: str, matches: list[str]) -> int:
    errors = 0
    for match in matches:
        filematch = _match_to_test_file(match)
        if not filematch.exists():
            ctx.error(
                f"The match '{match}' for rule '{rule}' points to a non "
                f"existing test module path: {filematch}"
            )
            errors += 1
    return errors


@cgroup.command(
    name="check",
)
def check(ctx: Context) -> None:
    exitcode = 0
    excludes = ("tools/", "templates/", ".nox/")
    full_filelist = [
        path.relative_to(tools.utils.REPO_ROOT)
        for path in tools.utils.REPO_ROOT.rglob("*.py")
    ]
    filelist = [
        str(path) for path in full_filelist if not str(path).startswith(excludes)
    ]
    filename_map = yaml.safe_load(FILENAME_MAP_PATH.read_text())
    for rule, matches in filename_map.items():
        if rule == "*":
            exitcode += _check_matches(ctx, rule, matches)
        elif "|" in rule:
            # This is regex
            for filepath in filelist:
                if re.match(rule, filepath):
                    # Found at least one match, stop looking
                    break
            else:
                ctx.error(
                    f"Could not find a matching file in the salt repo for the rule '{rule}'"
                )
                exitcode += 1
                continue
            exitcode += _check_matches(ctx, rule, matches)
        elif "*" in rule or "\\" in rule:
            # Glob matching
            process_matches = True
            for filerule in tools.utils.REPO_ROOT.glob(rule):
                if not filerule.exists():
                    ctx.error(
                        f"The rule '{rule}' points to a non existing path: {filerule}"
                    )
                    exitcode += 1
                    process_matches = False
            if process_matches:
                exitcode += _check_matches(ctx, rule, matches)
        else:
            # Direct file paths as rules
            filerule = pathlib.Path(rule)
            if not filerule.exists():
                ctx.error(
                    f"The rule '{rule}' points to a non existing path: {filerule}"
                )
                exitcode += 1
                continue
            exitcode += _check_matches(ctx, rule, matches)
    if exitcode:
        ctx.error(f"Found {exitcode} errors")
    ctx.exit(exitcode)
