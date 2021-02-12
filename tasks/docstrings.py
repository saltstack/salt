"""
    tasks.docstrings
    ~~~~~~~~~~~~~~~~

    Docstrings related tasks
"""

import ast
import pathlib
import re

from invoke import task  # pylint: disable=3rd-party-module-not-gated
from salt.loader import SALT_INTERNAL_LOADERS_PATHS
from salt.version import SaltStackVersion
from tasks import utils

CODE_DIR = pathlib.Path(__file__).resolve().parent.parent
SALT_CODE_DIR = CODE_DIR / "salt"
SALT_MODULES_PATH = SALT_CODE_DIR / "modules"


@task(iterable=["files"], positional=["files"])
def check(ctx, files, check_proper_formatting=False):
    """
    Check salt's docstrings
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
        _files = SALT_CODE_DIR.rglob("*.py")
    else:
        _files = [pathlib.Path(fname) for fname in _files]

    _files = [path.resolve() for path in _files]

    errors = 0
    exitcode = 0
    for path in _files:
        contents = path.read_text()
        try:
            module = ast.parse(path.read_text(), filename=str(path))
            module_docstring = ast.get_docstring(module, clean=False)
            if module_docstring:
                error = _check_valid_versions_on_docstrings(module_docstring)
                if error:
                    errors += 1
                    exitcode = 1
                    utils.error(
                        "The module '{}' does not provide a proper `{}` version: {!r} is not valid.",
                        path.relative_to(CODE_DIR),
                        *error,
                    )

            for funcdef in [
                node for node in module.body if isinstance(node, ast.FunctionDef)
            ]:
                docstring = ast.get_docstring(funcdef, clean=False)
                if docstring:
                    error = _check_valid_versions_on_docstrings(docstring)
                    if error:
                        errors += 1
                        exitcode = 1
                        utils.error(
                            "The module '{}' does not provide a proper `{}` version: {!r} is not valid.",
                            path.relative_to(CODE_DIR),
                            *error,
                        )

                if not str(path).startswith(SALT_INTERNAL_LOADERS_PATHS):
                    # No further docstrings checks are needed
                    continue

                # We're dealing with a salt loader module
                if funcdef.name.startswith("_"):
                    # We're not interested in internal functions
                    continue

                if not docstring:
                    errors += 1
                    exitcode = 1
                    utils.error(
                        "The function {!r} on '{}' does not have a docstring",
                        funcdef.name,
                        path.relative_to(CODE_DIR),
                    )
                    continue

                try:
                    relpath = path.relative_to(SALT_MODULES_PATH)
                    if str(relpath.parent) != ".":
                        # We don't want to check nested packages
                        continue
                    # But this is a module under salt/modules, let's check
                    # the CLI examples
                except ValueError:
                    # We're not checking CLI examples in any other salt loader modules
                    continue

                if _check_cli_example_present(docstring) is False:
                    errors += 1
                    exitcode = 1
                    utils.error(
                        "The function {!r} on '{}' does not have a 'CLI Example:' in it's docstring",
                        funcdef.name,
                        path.relative_to(CODE_DIR),
                    )
                    continue

                if check_proper_formatting is False:
                    continue

                # By now we now this function has a docstring and it has a CLI Example section
                # Let's now check if it's properly formatted
                if _check_cli_example_proper_formatting(docstring) is False:
                    errors += 1
                    exitcode = 1
                    utils.error(
                        "The function {!r} on '{}' does not have a proper 'CLI Example:' section in "
                        "it's docstring. The proper format is:\n"
                        "CLI Example:\n"
                        "\n"
                        ".. code-block:: bash\n"
                        "\n"
                        "    salt '*' <insert example here>\n",
                        funcdef.name,
                        path.relative_to(CODE_DIR),
                    )
                    continue
        finally:
            if contents != path.read_text():
                path.write_text(contents)

    if exitcode:
        utils.error("Found {} errors", errors)
    utils.exit_invoke(exitcode)


CHECK_VALID_VERSION_RE = re.compile(
    "(?P<vtype>(versionadded|versionchanged|deprecated))::(?P<version>.*)"
)


def _check_valid_versions_on_docstrings(docstring):
    for match in CHECK_VALID_VERSION_RE.finditer(docstring):
        vtype = match.group("vtype")
        version = match.group("version")
        versions = [vs.strip() for vs in version.split(",")]
        bad_versions = []
        for vs in versions:
            try:
                SaltStackVersion.parse(vs)
            except ValueError:
                bad_versions.append(vs)
        if bad_versions:
            return vtype, ", ".join(bad_versions)
    return False


CLI_EXAMPLE_PRESENT_RE = re.compile(r"CLI Example(?:s)?:")


def _check_cli_example_present(docstring):
    return CLI_EXAMPLE_PRESENT_RE.search(docstring) is not None


CLI_EXAMPLE_PROPER_FORMATTING_RE = re.compile(
    r"CLI Example(?:s)?:\n\n.. code-block:: bash\n\n    salt (.*) '*'", re.MULTILINE
)


def _check_cli_example_proper_formatting(docstring):
    return CLI_EXAMPLE_PROPER_FORMATTING_RE.search(docstring) is not None
