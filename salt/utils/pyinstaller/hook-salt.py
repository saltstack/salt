# pylint: disable=3rd-party-module-not-gated

import logging
import pathlib
import sys

from PyInstaller.utils import hooks

log = logging.getLogger(__name__)


def _filter_stdlib_tests(name):
    """
    Filter out non useful modules from the stdlib
    """
    if ".test." in name:
        return False
    if ".tests." in name:
        return False
    if ".idle_test" in name:
        return False
    return True


def _python_stdlib_path():
    """
    Return the path to the standard library folder
    """
    base_exec_prefix = pathlib.Path(sys.base_exec_prefix)
    log.info("Grabbing 'base_exec_prefix' for platform: %s", sys.platform)
    if not sys.platform.lower().startswith("win"):
        return base_exec_prefix / "lib" / "python{}.{}".format(*sys.version_info)
    return base_exec_prefix / "Lib"


def _collect_python_stdlib_hidden_imports():
    """
    Collect all of the standard library(most of it) as hidden imports.
    """
    _hidden_imports = set()

    stdlib = _python_stdlib_path()
    if not stdlib.exists():
        log.error("The path '%s' does not exist", stdlib)
        return list(_hidden_imports)

    log.info(
        "Collecting hidden imports from the python standard library at: %s",
        stdlib,
    )
    for path in stdlib.glob("*"):
        if path.is_dir():
            if path.name in (
                "__pycache__",
                "site-packages",
                "test",
                "turtledemo",
                "ensurepip",
            ):
                continue
            if path.joinpath("__init__.py").is_file():
                log.info("Collecting: %s", path.name)
                try:
                    _module_hidden_imports = hooks.collect_submodules(
                        path.name, filter=_filter_stdlib_tests
                    )
                    log.debug("Collected(%s): %s", path.name, _module_hidden_imports)
                    _hidden_imports.update(set(_module_hidden_imports))
                except Exception as exc:  # pylint: disable=broad-except
                    log.error("Failed to collect %r: %s", path.name, exc)
            continue
        if path.suffix not in (".py", ".pyc", ".pyo"):
            continue
        _hidden_imports.add(path.stem)
    log.info("Collected stdlib hidden imports: %s", sorted(_hidden_imports))
    return sorted(_hidden_imports)


def _collect_python_stdlib_dynamic_libraries():
    """
    Collect all of the standard library(most of it) dynamic libraries.
    """
    _dynamic_libs = set()

    stdlib = _python_stdlib_path()
    if not stdlib.exists():
        log.error("The path '%s' does not exist", stdlib)
        return list(_dynamic_libs)

    log.info(
        "Collecting dynamic libraries from the python standard library at: %s",
        stdlib,
    )
    for path in stdlib.glob("*"):
        if not path.is_dir():
            continue
        if path.name in (
            "__pycache__",
            "site-packages",
            "test",
            "turtledemo",
            "ensurepip",
        ):
            continue
        if path.joinpath("__init__.py").is_file():
            log.info("Collecting: %s", path.name)
            try:
                _module_dynamic_libs = hooks.collect_dynamic_libs(path.name, path.name)
                log.debug("Collected(%s): %s", path.name, _module_dynamic_libs)
                _dynamic_libs.update(set(_module_dynamic_libs))
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Failed to collect %r: %s", path.name, exc)
    log.info("Collected stdlib dynamic libs: %s", sorted(_dynamic_libs))
    return sorted(_dynamic_libs)


def _filter_submodules(name):
    # this should never happen, but serves as a place-holder for when/if we have to filter
    if not name.startswith("salt"):
        return False
    return True


# Collect Salt datas, binaries(should be None) and hidden imports
SALT_DATAS, SALT_BINARIES, SALT_HIDDENIMPORTS = hooks.collect_all(
    "salt",
    include_py_files=True,
    filter_submodules=_filter_submodules,
)

# In case there's salt-extensions installed, collect their datas and hidden imports
SALT_EXTENSIONS_DATAS, SALT_EXTENSIONS_HIDDENIMPORTS = hooks.collect_entry_point(
    "salt.loader"
)


# PyInstaller attributes
datas = sorted(set(SALT_DATAS + SALT_EXTENSIONS_DATAS))
binaries = sorted(set(SALT_BINARIES))
hiddenimports = sorted(
    set(
        SALT_HIDDENIMPORTS
        + SALT_EXTENSIONS_HIDDENIMPORTS
        + _collect_python_stdlib_hidden_imports()
    )
)
