"""
Check salt code base for for missing or wrong docs
"""

# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import ast
import collections
import os
import pathlib
import re

from ptscripts import Context, command_group

import tools.utils

DOCS_DIR = tools.utils.REPO_ROOT / "doc"
SALT_CODE_DIR = tools.utils.REPO_ROOT / "salt"

PYTHON_MODULE_TO_DOC_PATH = {}
DOC_PATH_TO_PYTHON_MODULE = {}


CHECK_PATHS = (
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
EXCLUDE_PATHS = (
    "salt/cloud/cli.py",
    "salt/cloud/exceptions.py",
    "salt/cloud/libcloudfuncs.py",
)

cgroup = command_group(name="docs", help=__doc__, parent="pre-commit")


def build_path_cache():
    """
    Build a python module to doc module cache
    """

    for path in SALT_CODE_DIR.rglob("*.py"):
        path = path.resolve().relative_to(tools.utils.REPO_ROOT)
        strpath = str(path)
        if strpath.endswith("__init__.py"):
            continue
        if not strpath.startswith(CHECK_PATHS):
            continue
        if strpath.startswith(EXCLUDE_PATHS):
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
                    stub_path / package / "all" / f"salt.netapi.{subpackage}.rst"
                )
        else:
            stub_path = (
                stub_path
                / package
                / "all"
                / str(path).replace(".py", ".rst").replace(os.sep, ".")
            )
        stub_path = stub_path.relative_to(tools.utils.REPO_ROOT)
        PYTHON_MODULE_TO_DOC_PATH[path] = stub_path
        if path.exists():
            DOC_PATH_TO_PYTHON_MODULE[stub_path] = path


build_path_cache()


def build_file_list(files, extension):
    if not files:
        _files = tools.utils.REPO_ROOT.rglob(f"*{extension}")
    else:
        _files = [fpath.resolve() for fpath in files if fpath.suffix == extension]
    _files = [path.relative_to(tools.utils.REPO_ROOT) for path in _files]
    return _files


def build_python_module_paths(files):
    _files = []
    for path in build_file_list(files, ".py"):
        strpath = str(path)
        if strpath.endswith("__init__.py"):
            continue
        if not strpath.startswith(CHECK_PATHS):
            continue
        if strpath.startswith(EXCLUDE_PATHS):
            continue
        _files.append(path)
    return _files


def build_docs_paths(files):
    return build_file_list(files, ".rst")


def check_inline_markup(ctx: Context, files: list[pathlib.Path]) -> int:
    """
    Check docstring for :doc: usage

    We should not be using the ``:doc:`` inline markup option when
    cross-referencing locations. Use ``:ref:`` or ``:mod:`` instead.

    This task checks for reference to ``:doc:`` usage.

    See Issue #12788 for more information.

    https://github.com/saltstack/salt/issues/12788
    """
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
                ctx.error(
                    f"The {funcdef.name} function in {path} contains ':doc:' usage"
                )
                exitcode += 1
    return exitcode


def check_stubs(ctx: Context, files: list[pathlib.Path]) -> int:
    files = build_python_module_paths(files)

    exitcode = 0
    for path in files:
        strpath = str(path)
        if strpath.endswith("__init__.py"):
            continue
        if not strpath.startswith(CHECK_PATHS):
            continue
        if strpath.startswith(EXCLUDE_PATHS):
            continue
        stub_path = PYTHON_MODULE_TO_DOC_PATH[path]
        if not stub_path.exists():
            exitcode += 1
            ctx.error(
                f"The module at {path} does not have a sphinx stub at {stub_path}"
            )
    return exitcode


def check_virtual(ctx: Context, files: list[pathlib.Path]) -> int:
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
        try:
            contents = path.read_text()
        except Exception as exc:  # pylint: disable=broad-except
            ctx.error(f"Error while processing '{path}': {exc}")
            exitcode += 1
            continue
        if ".. _virtual-" in contents:
            try:
                python_module = DOC_PATH_TO_PYTHON_MODULE[path]
                ctx.error(
                    f"The doc file at {path} indicates that it's virtual, yet, "
                    f"there's a python module at {python_module} that will "
                    "shaddow it.",
                )
                exitcode += 1
            except KeyError:
                # This is what we're expecting
                continue
    return exitcode


def check_module_indexes(ctx: Context, files: list[pathlib.Path]) -> int:
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
            ctx.error(
                f"The autosummary mods in {path} are not properly sorted. Please sort them.",
            )

        module_index_duplicates = [
            mod for mod, count in collections.Counter(module_index).items() if count > 1
        ]
        if module_index_duplicates:
            exitcode += 1
            ctx.error(
                f"Module index {path} contains duplicates: {module_index_duplicates}"
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
        if package == "configuration" and path_parts == ["logging"]:
            package = "log_handlers"
            path_parts = []
        python_package = SALT_CODE_DIR.joinpath(package, *path_parts).relative_to(
            tools.utils.REPO_ROOT
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
                    modules.add(f"{module.parent.stem}.{module.stem}")
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
            ctx.error(
                f"The module index at {path} is missing the following modules: "
                f"{', '.join(missing_modules_in_index)}"
            )
        extra_modules_in_index = set(module_index) - set(modules)
        if extra_modules_in_index:
            exitcode += 1
            ctx.error(
                f"The module index at {path} has extra modules(non existing): "
                f"{', '.join(extra_modules_in_index)}"
            )
    return exitcode


def check_stray(ctx: Context, files: list[pathlib.Path]) -> int:
    exitcode = 0
    exclude_pathlib_paths: tuple[pathlib.Path, ...]
    exclude_paths: tuple[str, ...]

    exclude_pathlib_paths = (
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
    exclude_paths = tuple(
        str(p.relative_to(tools.utils.REPO_ROOT)) for p in exclude_pathlib_paths
    )
    files = build_docs_paths(files)
    for path in files:
        if not str(path).startswith(
            str((DOCS_DIR / "ref").relative_to(tools.utils.REPO_ROOT))
        ):
            continue
        if str(path).startswith(exclude_paths):
            continue
        if path.name in ("index.rst", "glossary.rst", "faq.rst", "README.rst"):
            continue
        if path not in DOC_PATH_TO_PYTHON_MODULE:
            contents = path.read_text()
            if ".. _virtual-" in contents:
                continue
            exitcode += 1
            ctx.error(
                f"The doc at {path} doesn't have a corresponding python module "
                "and is considered a stray doc. Please remove it."
            )
    return exitcode


@cgroup.command(
    name="check",
    arguments={
        "files": {
            "help": "List of files to check",
            "nargs": "*",
        }
    },
)
def check(ctx: Context, files: list[pathlib.Path]) -> None:
    exitcode = 0
    ctx.info("Checking inline :doc: markup")
    exitcode += check_inline_markup(ctx, files)
    ctx.info("Checking python module stubs")
    exitcode += check_stubs(ctx, files)
    ctx.info("Checking virtual modules")
    exitcode += check_virtual(ctx, files)
    ctx.info("Checking stray docs")
    exitcode += check_stray(ctx, files)
    ctx.info("Checking doc module indexes")
    exitcode += check_module_indexes(ctx, files)
    ctx.exit(exitcode)
