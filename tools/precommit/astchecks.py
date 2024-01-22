"""
These commands are used to run some custom AST checks on python code
"""
# pylint: disable=resource-leakage,broad-except,3rd-party-module-not-gated
from __future__ import annotations

import ast
import logging
import pathlib
import sys
from functools import lru_cache

from ptscripts import Context, command_group

import tools.utils

if sys.version_info < (3, 9, 2):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict  # type: ignore[attr-defined,no-redef]

log = logging.getLogger(__name__)


# Define the command group
cgroup = command_group(
    name="ast",
    help="AST Checks",
    description=__doc__,
    parent="pre-commit",
)


@cgroup.command(
    name="check",
    arguments={
        "files": {
            "nargs": "*",
        }
    },
)
def check_ast(ctx: Context, files: list[pathlib.Path]):
    exitcode = 0
    for fpath in files:
        ctx.debug(f"Checking {fpath} ...")
        try:
            tree = ast.parse(fpath.read_text())
        except (SyntaxError, ValueError):
            ctx.error(f"Failed to AST parse {fpath}")
            exitcode += 1
            continue
        exitcode += _run_checks(ctx, fpath, tree)
    ctx.exit(exitcode)


def _run_checks(ctx: Context, fpath: pathlib.Path, tree: ast.AST) -> int:
    checkers = [
        BadDunderUtilsUsage,
        UnnecessaryDunderVirtualInUtilsModule,
    ]
    errors = 0
    for checker in checkers:
        if checker.check_path(fpath.resolve()):
            if checker.__doc__:
                ctx.debug(f" * {checker.__doc__.strip()}")
            else:
                ctx.debug(f" * Running {checker.__class__.__name__} ...")
            checker_instance = checker(ctx, fpath)
            checker_instance.visit(tree)
            if checker_instance.check_failed():
                errors += 1
    return errors


class NodeVisitor(ast.NodeVisitor):
    """
    Base class for AST checks.
    """

    def __init__(self, ctx: Context, fpath: pathlib.Path):
        self.ctx = ctx
        self.fpath = fpath

    def log_error(self, node: ast.AST, message: str):
        self.ctx.error(f"{self.fpath}:{node.lineno}: {message}")

    @classmethod
    def check_path(cls, path: pathlib.Path) -> bool:
        try:
            path.relative_to(tools.utils.REPO_ROOT, "salt")

            return True
        except ValueError:
            return False

    def check_failed(self):
        raise NotImplementedError


class BadDunderUtilsUsage(NodeVisitor):
    """
    Validate __utils__ usage.
    """

    def __init__(self, ctx: Context, fpath: pathlib.Path):
        super().__init__(ctx, fpath)
        self._failed_checks = False

    def check_failed(self):
        return self._failed_checks

    def visit_Compare(self, node: ast.Compare):
        if not isinstance(node.left, ast.Constant):
            return
        for comp in node.comparators:
            if not isinstance(comp, ast.Name):
                continue
            if comp.id == "__utils__":
                modname, func = node.left.value.split(".")
                try:
                    info = get_utils_module_info(modname)
                except RuntimeError as exc:
                    self.log_error(
                        node,
                        f"{exc} Please fix the code [yellow]{ast.unparse(node)}[/yellow]",
                    )
                    self._failed_checks = True
                else:
                    if not info["uses_salt_dunders"]:
                        self.log_error(
                            node,
                            f"The {modname} is not loaded by the __utils__ loader."
                            f"Use alternate means for the check: {ast.unparse(node)}",
                        )
                        self._failed_checks = True
        return self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript):
        if not isinstance(node.value, ast.Name):
            return self.generic_visit(node)
        if not node.value.id == "__utils__":
            return self.generic_visit(node)
        if not isinstance(node.slice, ast.Constant):
            return self.generic_visit(node)
        # print(self.fpath, node.lineno)
        # print(ast.dump(node, indent=4))
        modname, funcname = node.slice.value.split(".")
        try:
            info = get_utils_module_info(modname)
        except RuntimeError as exc:
            self.log_error(
                node, f"{exc} Please fix the code [yellow]{ast.unparse(node)}[/yellow]"
            )
            self._failed_checks = True
        else:
            if not info["uses_salt_dunders"]:
                self.log_error(
                    node,
                    f"The {modname} is not loaded by the __utils__ loader."
                    f"Use alternate means for the check: {ast.unparse(node)}",
                )
                self._failed_checks = True


class UnnecessaryDunderVirtualInUtilsModule(NodeVisitor):
    """
    Validate __virtual__ definition in 'salt/utils/*.py' module
    """

    SALT_DUNDERS = (
        "__active_provider_name__",
        "__context__",
        "__env__",
        "__events__",
        "__executors__",
        "__grains__",
        "__instance_id__",
        "__jid_event__",
        "__low__",
        "__lowstate__",
        "__master_opts__",
        "__opts__",
        "__pillar__",
        "__proxy__",
        "__reg__",
        "__ret__",
        "__runner__",
        "__running__",
        "__salt__",
        "__salt_system_encoding__",
        "__serializers__",
        "__states__",
        "__utils__",
    )
    LOADER_MODULE_FUNCS = (
        "__init__",
        "__virtual__",
    )
    LOADER_MODULE_ATTRS = (
        "__virtualname__",
        "__func_alias__",
        "__salt_loader__",
    )

    def __init__(self, ctx: Context, fpath: pathlib.Path):
        super().__init__(ctx, fpath)
        self.uses_salt_dunders = False
        self.defined_loader_attrs: set[str] = set()
        self.defined_loader_funcs: set[str] = set()
        self._in_class_def = False

    @classmethod
    def check_path(cls, path: pathlib.Path) -> bool:
        try:
            path.relative_to(tools.utils.REPO_ROOT, "salt", "utils")

            return True
        except ValueError:
            return False

    def check_failed(self):
        failed = False
        if not self.uses_salt_dunders:
            if self.defined_loader_attrs or self.defined_loader_funcs:
                failed = True
                for attrname in self.defined_loader_attrs:
                    self.log_error(
                        self.tree,
                        f"Don't define a '{attrname}' attribute in '{self.fpath}'",
                    )
                for funcname in self.defined_loader_funcs:
                    self.log_error(
                        self.tree,
                        f"Don't define a '{funcname}' function in '{self.fpath}'",
                    )
        return failed

    def visit_Name(self, node: ast.Name):
        if node.id in self.SALT_DUNDERS:
            self.uses_salt_dunders = True
        if node.id in self.LOADER_MODULE_ATTRS:
            self.defined_loader_attrs.add(node.id)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self._in_class_def = True
        try:
            return self.generic_visit(node)
        finally:
            self._in_class_def = False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if not self._in_class_def and node.name in self.LOADER_MODULE_FUNCS:
            self.defined_loader_funcs.add(node.name)
        return self.generic_visit(node)


@lru_cache
def get_utils_module_info(modname: str) -> ModuleInfo:
    details: ModuleInfo | None = None
    for details in get_utils_modules_info().values():
        if details["modname"] == modname:
            break
        if details["virtualname"] == modname:
            break
    else:
        raise RuntimeError(f"Could not find utils module {modname!r} information.")
    return details


class ModuleInfo(TypedDict):
    modname: str
    virtualname: str
    uses_salt_dunders: bool


@lru_cache
def get_utils_modules_info() -> dict[pathlib.Path, ModuleInfo]:
    """
    Collect utils modules dunder information.
    """
    mapping: dict[pathlib.Path, ModuleInfo] = {}
    salt_utils_package_path = tools.utils.REPO_ROOT / "salt" / "utils"
    for path in salt_utils_package_path.rglob("*.py"):
        visitor = DunderParser()
        tree = ast.parse(path.read_text())
        visitor.visit(tree)
        mapping[path.resolve()] = ModuleInfo(
            modname=path.stem,
            virtualname=visitor.virtualname or path.stem,
            uses_salt_dunders=visitor.uses_salt_dunders,
        )
    return mapping


class DunderParser(ast.NodeVisitor):
    def __init__(self):
        self.virtualname = None
        self.uses_salt_dunders = False

    def visit_Name(self, node):
        if node.id in UnnecessaryDunderVirtualInUtilsModule.SALT_DUNDERS:
            self.uses_salt_dunders = True

    def visit_Assign(self, node):
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "__virtualname__":
                self.virtualname = node.value.s
