"""
    tasks.imports
    ~~~~~~~~~~~~~

    Imports related tasks
"""

import pathlib
import re

from invoke import task  # pylint: disable=3rd-party-module-not-gated
from tasks import utils

CODE_DIR = pathlib.Path(__file__).resolve().parent.parent
SALT_CODE_DIR = CODE_DIR / "salt"


@task(iterable=["files"], positional=["files"])
def remove_comments(ctx, files):
    """
    Remove import comments, 'Import Python libs', 'Import salt libs', etc
    """
    # CD into Salt's repo root directory
    ctx.cd(CODE_DIR)

    # Unfortunately invoke does not support nargs.
    # We migth have been passed --files="foo.py bar.py"
    # Turn that into a list of paths
    _files = []
    for path in files:
        if not path:
            continue
        _files.extend(path.split())
    if not _files:
        utils.exit_invoke(0)

    _files = [
        pathlib.Path(fname).resolve() for fname in _files if fname.endswith(".py")
    ]

    fixes = 0
    exitcode = 0
    comments_regex = re.compile(r"^# ([I|i])mports? .*(([L|l])ibs?)?\n", re.MULTILINE)
    for path in _files:
        contents = path.read_text()
        fixed = comments_regex.sub("", contents)
        if fixed == contents:
            continue
        fixes += 1
        exitcode = 1
        path.write_text(fixed)
    if exitcode:
        utils.error("Fixed {} files", fixes)
    utils.exit_invoke(exitcode)
