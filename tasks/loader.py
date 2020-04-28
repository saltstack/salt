# -*- coding: utf-8 -*-
"""
    tasks.loader
    ~~~~~~~~~~~~

    Salt loader checks
"""

import ast
import pathlib

from invoke import task  # pylint: disable=3rd-party-module-not-gated
from tasks import utils

CODE_DIR = pathlib.Path(__file__).resolve().parent.parent
SALT_CODE_DIR = CODE_DIR / "salt"


@task(iterable=["files"], positional=["files"])
def check_virtual(ctx, files):
    """
    Check Salt loader modules for a defined `__virtualname__` attribute and `__virtual__` function.

    This is meant to replace:

        https://github.com/saltstack/salt/blob/27ae8260983b11fe6e32a18e777d550be9fe1dc2/tests/unit/test_virtualname.py
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

    salt_loaders = (
        CODE_DIR / "salt" / "modules",
        CODE_DIR / "salt" / "metaproxy",
        CODE_DIR / "salt" / "matchers",
        CODE_DIR / "salt" / "engines",
        CODE_DIR / "salt" / "proxy",
        CODE_DIR / "salt" / "returners",
        CODE_DIR / "salt" / "utils",
        CODE_DIR / "salt" / "pillar",
        CODE_DIR / "salt" / "tops",
        CODE_DIR / "salt" / "wheel",
        CODE_DIR / "salt" / "output",
        CODE_DIR / "salt" / "serializers",
        CODE_DIR / "salt" / "tokens",
        CODE_DIR / "salt" / "auth",
        CODE_DIR / "salt" / "fileserver",
        CODE_DIR / "salt" / "roster",
        CODE_DIR / "salt" / "thorium",
        CODE_DIR / "salt" / "states",
        CODE_DIR / "salt" / "beacons",
        CODE_DIR / "salt" / "log" / "handlers",
        CODE_DIR / "salt" / "client" / "ssh",
        CODE_DIR / "salt" / "renderers",
        CODE_DIR / "salt" / "grains",
        CODE_DIR / "salt" / "runners",
        CODE_DIR / "salt" / "queues",
        CODE_DIR / "salt" / "sdb",
        CODE_DIR / "salt" / "spm" / "pkgdb",
        CODE_DIR / "salt" / "spm" / "pkgfiles",
        CODE_DIR / "salt" / "cloud" / "clouds",
        CODE_DIR / "salt" / "netapi",
        CODE_DIR / "salt" / "executors",
        CODE_DIR / "salt" / "cache",
    )

    # This is just internal task checking
    for loader in salt_loaders:
        if not pathlib.Path(loader).is_dir():
            utils.error("The {} path is not a directory", loader)

    errors = 0
    exitcode = 0
    for path in _files:
        strpath = str(path)
        if strpath.endswith("__init__.py"):
            continue
        for loader in salt_loaders:
            try:
                path.relative_to(loader)
                break
            except ValueError:
                # Path doesn't start with the loader path, carry on
                continue
        module = ast.parse(path.read_text(), filename=strpath)
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
                            if node.value.s not in path.name:
                                errors += 1
                                exitcode = 1
                                utils.error(
                                    'The value of the __virtualname__ attribute, "{}" is not part of {}',
                                    node.value.s,
                                    path.name,
                                )
            if found_virtualname_attr:
                break

        if not found_virtualname_attr:
            errors += 1
            exitcode = 1
            utils.error(
                "The salt loader module {} defines a __virtual__() function but does not define a "
                "__virtualname__ attribute",
                path.relative_to(CODE_DIR),
            )
    if exitcode:
        utils.error("Found {} errors", errors)
    utils.exit_invoke(exitcode)
