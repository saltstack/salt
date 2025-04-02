"""
Salt loader checks
"""

import ast
import pathlib

from ptscripts import Context, command_group

import tools.utils
from tools.precommit import SALT_INTERNAL_LOADERS_PATHS

SALT_CODE_DIR = tools.utils.REPO_ROOT / "salt"

cgroup = command_group(name="salt-loaders", help=__doc__, parent="pre-commit")


@cgroup.command(
    name="check-virtual",
    arguments={
        "files": {
            "help": "List of files to check",
            "nargs": "*",
        },
        "enforce_virtualname": {
            "help": "Enforce the usage of `__virtualname__`",
        },
    },
)
def check_virtual(
    ctx: Context, files: list[pathlib.Path], enforce_virtualname: bool = False
) -> None:
    """
    Check Salt loader modules for a defined `__virtualname__` attribute and `__virtual__` function.

    This is meant to replace:

        https://github.com/saltstack/salt/blob/27ae8260983b11fe6e32a18e777d550be9fe1dc2/tests/unit/test_virtualname.py
    """
    if not files:
        _files = list(SALT_CODE_DIR.rglob("*.py"))
    else:
        _files = [fpath.resolve() for fpath in files if fpath.suffix == ".py"]

    errors = 0
    exitcode = 0
    for path in _files:
        strpath = str(path)
        if path.name == "__init__.py":
            continue
        for loader in SALT_INTERNAL_LOADERS_PATHS:
            try:
                path.relative_to(loader)
                break
            except ValueError:
                # Path doesn't start with the loader path, carry on
                continue
        module = ast.parse(path.read_text(), filename=str(path))
        found_virtual_func = False
        for funcdef in [
            node for node in module.body if isinstance(node, ast.FunctionDef)
        ]:
            if funcdef.name == "__virtual__":
                found_virtual_func = True
                break
        if not found_virtual_func:
            # If the module does not define a __virtual__() function, we don't require a __virtualname__ attribute
            continue

        found_virtualname_attr = False
        for node in module.body:
            if isinstance(node, ast.Assign):
                if not found_virtualname_attr:
                    for target in node.targets:
                        if not isinstance(target, ast.Name):
                            continue
                        if target.id == "__virtualname__":
                            found_virtualname_attr = True
                            if node.value.s not in path.name:  # type: ignore[attr-defined]
                                errors += 1
                                exitcode = 1
                                ctx.error(
                                    'The value of the __virtualname__ attribute, "{}"'
                                    " is not part of {}".format(
                                        node.value.s,  # type: ignore[attr-defined]
                                        path.name,
                                    )
                                )
            if found_virtualname_attr:
                break

        if not found_virtualname_attr and enforce_virtualname:
            errors += 1
            exitcode = 1
            ctx.error(
                f"The salt loader module {path.relative_to(tools.utils.REPO_ROOT)} defines "
                "a __virtual__() function but does not define a __virtualname__ attribute"
            )
    if exitcode:
        ctx.error(f"Found {errors} errors")
    ctx.exit(exitcode)
