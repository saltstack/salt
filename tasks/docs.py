# -*- coding: utf-8 -*-
"""
    tasks.docstrings
    ~~~~~~~~~~~~~~~~

    Check salt code base for for missing or wrong docstrings
"""

import ast
import collections
import os
import pathlib
import re

from invoke import task  # pylint: disable=3rd-party-module-not-gated
from tasks import utils

CODE_DIR = pathlib.Path(__file__).resolve().parent.parent
DOCS_DIR = CODE_DIR / "doc"
SALT_CODE_DIR = CODE_DIR / "salt"

os.chdir(str(CODE_DIR))

python_module_to_doc_path = {}
doc_path_to_python_module = {}


check_paths = (
    "salt/auth",
    "salt/beacons",
    "salt/cache",
    "salt/cloud",
    "salt/engine",
    "salt/executors",
    "salt/fileserver",
    "salt/grains",
    "salt/modules",
    "salt/netapi",
    "salt/output",
    "salt/pillar",
    "salt/proxy",
    "salt/queues",
    "salt/renderers",
    "salt/returners",
    "salt/roster",
    "salt/runners",
    "salt/sdb",
    "salt/serializers",
    "salt/states",
    "salt/thorium",
    "salt/tokens",
    "salt/tops",
    "salt/wheel",
)
exclude_paths = (
    "salt/cloud/cli.py",
    "salt/cloud/exceptions.py",
    "salt/cloud/libcloudfuncs.py",
)


def build_path_cache():
    """
    Build a python module to doc module cache
    """

    for path in SALT_CODE_DIR.rglob("*.py"):
        path = path.resolve().relative_to(CODE_DIR)
        strpath = str(path)
        if strpath.endswith("__init__.py"):
            continue
        if not strpath.startswith(check_paths):
            continue
        if strpath.startswith(exclude_paths):
            continue

        parts = list(path.parts)
        stub_path = DOCS_DIR / "ref"
        # Remove salt from parts
        parts.pop(0)
        # Remove the package from parts
        package = parts.pop(0)
        # Remove the module from parts
        module = parts.pop()

        if package == "cloud":
            package = "clouds"
        if package == "fileserver":
            package = "file_server"
        if package == "netapi":
            # These are handled differently
            if not parts:
                # This is rest_wsgi
                stub_path = (
                    stub_path
                    / package
                    / "all"
                    / str(path).replace(".py", ".rst").replace(os.sep, ".")
                )
            else:
                # rest_cherrypy, rest_tornado
                subpackage = parts.pop(0)
                stub_path = (
                    stub_path
                    / package
                    / "all"
                    / "salt.netapi.{}.rst".format(subpackage)
                )
        else:
            stub_path = (
                stub_path
                / package
                / "all"
                / str(path).replace(".py", ".rst").replace(os.sep, ".")
            )
        stub_path = stub_path.relative_to(CODE_DIR)
        python_module_to_doc_path[path] = stub_path
        doc_path_to_python_module[stub_path] = path


build_path_cache()


def build_file_list(files, extension):
    # Unfortunately invoke does not support nargs.
    # We migth have been passed --files="foo.py bar.py"
    # Turn that into a list of paths
    _files = []
    for path in files:
        if not path:
            continue
        for spath in path.split():
            if not spath.endswith(extension):
                continue
            _files.append(spath)
    if not _files:
        _files = CODE_DIR.rglob("*{}".format(extension))
    else:
        _files = [pathlib.Path(fname).resolve() for fname in _files]
    _files = [path.relative_to(CODE_DIR) for path in _files]
    return _files


def build_python_module_paths(files):
    _files = []
    for path in build_file_list(files, ".py"):
        strpath = str(path)
        if strpath.endswith("__init__.py"):
            continue
        if not strpath.startswith(check_paths):
            continue
        if strpath.startswith(exclude_paths):
            continue
        _files.append(path)
    return _files


def build_docs_paths(files):
    return build_file_list(files, ".rst")


@task(iterable=["files"], positional=["files"])
def check_inline_markup(ctx, files):
    """
    Check docstring for :doc: usage

    We should not be using the ``:doc:`` inline markup option when
    cross-referencing locations. Use ``:ref:`` or ``:mod:`` instead.

    This task checks for reference to ``:doc:`` usage.

    See Issue #12788 for more information.

    https://github.com/saltstack/salt/issues/12788
    """
    # CD into Salt's repo root directory
    ctx.cd(CODE_DIR)

    files = build_python_module_paths(files)

    exitcode = 0
    for path in files:
        module = ast.parse(path.read_text(), filename=str(path))
        funcdefs = [node for node in module.body if isinstance(node, ast.FunctionDef)]
        for funcdef in funcdefs:
            docstring = ast.get_docstring(funcdef, clean=True)
            if not docstring:
                continue
            if ":doc:" in docstring:
                utils.error(
                    "The {} function in {} contains ':doc:' usage", funcdef.name, path
                )
                exitcode += 1
    utils.exit_invoke(exitcode)


@task(iterable=["files"])
def check_stubs(ctx, files):
    # CD into Salt's repo root directory
    ctx.cd(CODE_DIR)

    files = build_python_module_paths(files)

    exitcode = 0
    for path in files:
        strpath = str(path)
        if strpath.endswith("__init__.py"):
            continue
        if not strpath.startswith(check_paths):
            continue
        if strpath.startswith(exclude_paths):
            continue
        stub_path = python_module_to_doc_path[path]
        if not stub_path.exists():
            exitcode += 1
            utils.error(
                "The module at {} does not have a sphinx stub at {}", path, stub_path
            )
    utils.exit_invoke(exitcode)


@task(iterable=["files"])
def check_virtual(ctx, files):
    """
    Check if .rst files for each module contains the text ".. _virtual"
    indicating it is a virtual doc page, and, in case a module exists by
    the same name, it's going to be shaddowed and not accessible
    """
    exitcode = 0
    files = build_docs_paths(files)
    for path in files:
        if path.name == "index.rst":
            continue
        contents = path.read_text()
        if ".. _virtual-" in contents:
            try:
                python_module = doc_path_to_python_module[path]
                utils.error(
                    "The doc file at {} indicates that it's virtual, yet, there's a python module "
                    "at {} that will shaddow it.",
                    path,
                    python_module,
                )
                exitcode += 1
            except KeyError:
                # This is what we're expecting
                continue
    utils.exit_invoke(exitcode)


@task(iterable=["files"])
def check_module_indexes(ctx, files):
    exitcode = 0
    files = build_docs_paths(files)
    for path in files:
        if path.name != "index.rst":
            continue
        contents = path.read_text()
        if ".. autosummary::" not in contents:
            continue
        module_index_block = re.search(
            r"""
            \.\.\s+autosummary::\s*\n
            (\s+:[a-z]+:.*\n)*
            (\s*\n)+
            (?P<mods>(\s*[a-z0-9_\.]+\s*\n)+)
        """,
            contents,
            flags=re.VERBOSE,
        )

        if not module_index_block:
            continue

        module_index = re.findall(
            r"""\s*([a-z0-9_\.]+)\s*\n""", module_index_block.group("mods")
        )
        if module_index != sorted(module_index):
            exitcode += 1
            utils.error(
                "The autosummary mods in {} are not properly sorted. Please sort them.",
                path,
            )

        module_index_duplicates = [
            mod for mod, count in collections.Counter(module_index).items() if count > 1
        ]
        if module_index_duplicates:
            exitcode += 1
            utils.error(
                "Module index {} contains duplicates: {}", path, module_index_duplicates
            )
        # Let's check if all python modules are included in the index
        path_parts = list(path.parts)
        # drop doc
        path_parts.pop(0)
        # drop ref
        path_parts.pop(0)
        # drop "index.rst"
        path_parts.pop()
        # drop "all"
        path_parts.pop()
        package = path_parts.pop(0)
        if package == "clouds":
            package = "cloud"
        if package == "file_server":
            package = "fileserver"
        if package == "configuration":
            package = "log"
            path_parts = ["handlers"]
        python_package = SALT_CODE_DIR.joinpath(package, *path_parts).relative_to(
            CODE_DIR
        )
        modules = set()
        for module in python_package.rglob("*.py"):
            if package == "netapi":
                if module.stem == "__init__":
                    continue
                if len(module.parts) > 4:
                    continue
                if len(module.parts) > 3:
                    modules.add(module.parent.stem)
                else:
                    modules.add(module.stem)
            elif package == "cloud":
                if len(module.parts) < 4:
                    continue
                if module.name == "__init__.py":
                    continue
                modules.add(module.stem)
            elif package == "modules":
                if len(module.parts) > 3:
                    # salt.modules.inspeclib
                    if module.name == "__init__.py":
                        modules.add(module.parent.stem)
                        continue
                    modules.add("{}.{}".format(module.parent.stem, module.stem))
                    continue
                if module.name == "__init__.py":
                    continue
                modules.add(module.stem)
            elif module.name == "__init__.py":
                continue
            elif module.name != "__init__.py":
                modules.add(module.stem)

        missing_modules_in_index = set(modules) - set(module_index)
        if missing_modules_in_index:
            exitcode += 1
            utils.error(
                "The module index at {} is missing the following modules: {}",
                path,
                ", ".join(missing_modules_in_index),
            )
        extra_modules_in_index = set(module_index) - set(modules)
        if extra_modules_in_index:
            exitcode += 1
            utils.error(
                "The module index at {} has extra modules(non existing): {}",
                path,
                ", ".join(extra_modules_in_index),
            )
    utils.exit_invoke(exitcode)


@task(iterable=["files"])
def check_stray(ctx, files):
    exitcode = 0
    exclude_paths = (
        DOCS_DIR / "_inc",
        DOCS_DIR / "ref" / "cli" / "_includes",
        DOCS_DIR / "ref" / "cli",
        DOCS_DIR / "ref" / "configuration",
        DOCS_DIR / "ref" / "file_server" / "backends.rst",
        DOCS_DIR / "ref" / "file_server" / "environments.rst",
        DOCS_DIR / "ref" / "file_server" / "file_roots.rst",
        DOCS_DIR / "ref" / "internals",
        DOCS_DIR / "ref" / "modules" / "all" / "salt.modules.inspectlib.rst",
        DOCS_DIR / "ref" / "peer.rst",
        DOCS_DIR / "ref" / "publisheracl.rst",
        DOCS_DIR / "ref" / "python-api.rst",
        DOCS_DIR / "ref" / "states" / "aggregate.rst",
        DOCS_DIR / "ref" / "states" / "altering_states.rst",
        DOCS_DIR / "ref" / "states" / "backup_mode.rst",
        DOCS_DIR / "ref" / "states" / "compiler_ordering.rst",
        DOCS_DIR / "ref" / "states" / "extend.rst",
        DOCS_DIR / "ref" / "states" / "failhard.rst",
        DOCS_DIR / "ref" / "states" / "global_state_arguments.rst",
        DOCS_DIR / "ref" / "states" / "highstate.rst",
        DOCS_DIR / "ref" / "states" / "include.rst",
        DOCS_DIR / "ref" / "states" / "layers.rst",
        DOCS_DIR / "ref" / "states" / "master_side.rst",
        DOCS_DIR / "ref" / "states" / "ordering.rst",
        DOCS_DIR / "ref" / "states" / "parallel.rst",
        DOCS_DIR / "ref" / "states" / "providers.rst",
        DOCS_DIR / "ref" / "states" / "requisites.rst",
        DOCS_DIR / "ref" / "states" / "startup.rst",
        DOCS_DIR / "ref" / "states" / "testing.rst",
        DOCS_DIR / "ref" / "states" / "top.rst",
        DOCS_DIR / "ref" / "states" / "vars.rst",
        DOCS_DIR / "ref" / "states" / "writing.rst",
        DOCS_DIR / "topics",
    )
    exclude_paths = tuple([str(p.relative_to(CODE_DIR)) for p in exclude_paths])
    files = build_docs_paths(files)
    for path in files:
        if not str(path).startswith(str((DOCS_DIR / "ref").relative_to(CODE_DIR))):
            continue
        if str(path).startswith(exclude_paths):
            continue
        if path.name in ("index.rst", "glossary.rst", "faq.rst", "README.rst"):
            continue
        try:
            python_module = doc_path_to_python_module[path]
        except KeyError:
            contents = path.read_text()
            if ".. _virtual-" in contents:
                continue
            exitcode += 1
            utils.error(
                "The doc at {} doesn't have a corresponding python module an is considered a stray "
                "doc. Please remove it.",
                path,
            )
    utils.exit_invoke(exitcode)


@task(iterable=["files"])
def check(ctx, files):
    try:
        utils.info("Checking inline :doc: markup")
        check_inline_markup(ctx, files)
    except SystemExit as exc:
        if exc.code != 0:
            raise
    try:
        utils.info("Checking python module stubs")
        check_stubs(ctx, files)
    except SystemExit as exc:
        if exc.code != 0:
            raise
    try:
        utils.info("Checking virtual modules")
        check_virtual(ctx, files)
    except SystemExit as exc:
        if exc.code != 0:
            raise
    try:
        utils.info("Checking doc module indexes")
        check_module_indexes(ctx, files)
    except SystemExit as exc:
        if exc.code != 0:
            raise
    try:
        utils.info("Checking stray docs")
        check_stray(ctx, files)
    except SystemExit as exc:
        if exc.code != 0:
            raise
