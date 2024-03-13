"""
    tests.support.pytest.loader
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Salt's Loader PyTest Mock Support
"""

import logging
import sys
import types
from collections import deque

import attr

from tests.support.mock import patch

log = logging.getLogger(__name__)


@attr.s(init=True, slots=True, frozen=True)
class LoaderModuleMock:

    setup_loader_modules = attr.ib(init=True)
    # These dunders should always exist at the module global scope
    salt_module_dunders = attr.ib(
        init=True,
        repr=False,
        kw_only=True,
        default=(
            "__opts__",
            "__salt__",
            "__runner__",
            "__context__",
            "__utils__",
            "__ext_pillar__",
            "__thorium__",
            "__states__",
            "__serializers__",
            "__ret__",
            "__grains__",
            "__pillar__",
            "__sdb__",
        ),
    )
    # These dunders might exist at the module global scope
    salt_module_dunders_optional = attr.ib(
        init=True,
        repr=False,
        kw_only=True,
        default=("__proxy__",),
    )
    # These dunders might exist at the function global scope
    salt_module_dunder_attributes = attr.ib(
        init=True,
        repr=False,
        kw_only=True,
        default=(
            # Salt states attributes
            "__env__",
            "__low__",
            "__instance_id__",
            "__orchestration_jid__",
            # Salt runners attributes
            "__jid_event__",
            # Salt cloud attributes
            "__active_provider_name__",
            # Proxy Minions
            "__proxyenabled__",
        ),
    )
    _finalizers = attr.ib(
        init=False, repr=False, hash=False, default=attr.Factory(deque)
    )

    def start(self):
        module_globals = {dunder: {} for dunder in self.salt_module_dunders}
        for module, globals_to_mock in self.setup_loader_modules.items():
            log.trace(
                "Setting up loader globals for %s; globals: %s", module, globals_to_mock
            )
            if not isinstance(module, types.ModuleType):
                raise RuntimeError(
                    "The dictionary keys returned by setup_loader_modules() "
                    "must be an imported module, not {}".format(type(module))
                )
            if not isinstance(globals_to_mock, dict):
                raise RuntimeError(
                    "The dictionary values returned by setup_loader_modules() "
                    "must be a dictionary, not {}".format(type(globals_to_mock))
                )
            for key in self.salt_module_dunders:
                if not hasattr(module, key):
                    # Set the dunder name as an attribute on the module if not present
                    setattr(module, key, {})
                    # Remove the added attribute after the test finishes
                    self.addfinalizer(delattr, module, key)

            # Patch sys.modules as the first step
            self._patch_sys_modules(globals_to_mock)

            # Now patch the module globals
            # We actually want to grab a copy of the module globals so that if mocking
            # multiple modules, and at least one of the modules has a function to path,
            # the patch only happens on the module it's supposed to patch and not all of them.
            # It's not a deepcopy because we want to maintain the reference to the salt dunders
            # added in the start of this function
            self._patch_module_globals(module, globals_to_mock, module_globals.copy())

    def stop(self):
        while self._finalizers:
            func, args, kwargs = self._finalizers.popleft()
            func_repr = self._format_callback(func, args, kwargs)
            try:
                log.trace("Calling finalizer %s", func_repr)
                func(*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                log.error(
                    "Failed to run finalizer %s: %s",
                    func_repr,
                    exc,
                    exc_info=True,
                )

    def addfinalizer(self, func, *args, **kwargs):
        """
        Register a function to run when stopping
        """
        self._finalizers.append((func, args, kwargs))

    def _format_callback(self, callback, args, kwargs):
        callback_str = f"{callback.__qualname__}("
        if args:
            callback_str += ", ".join([repr(arg) for arg in args])
        if kwargs:
            callback_str += ", ".join([f"{k}={v!r}" for (k, v) in kwargs.items()])
        callback_str += ")"
        return callback_str

    def _patch_sys_modules(self, mocks):
        if "sys.modules" not in mocks:
            return
        sys_modules = mocks["sys.modules"]
        if not isinstance(sys_modules, dict):
            raise RuntimeError(
                f"'sys.modules' must be a dictionary not: {type(sys_modules)}"
            )
        patcher = patch.dict(sys.modules, values=sys_modules)
        patcher.start()
        self.addfinalizer(patcher.stop)

    def _patch_module_globals(self, module, mocks, module_globals):
        salt_dunder_dicts = self.salt_module_dunders + self.salt_module_dunders_optional
        allowed_salt_dunders = salt_dunder_dicts + self.salt_module_dunder_attributes
        for key in mocks:
            if key == "sys.modules":
                # sys.modules is addressed on another function
                continue

            if key.startswith("__"):
                if key in ("__init__", "__virtual__"):
                    raise RuntimeError(
                        "No need to patch {!r}. Passed loader module dict: {}".format(
                            key,
                            self.setup_loader_modules,
                        )
                    )
                elif key not in allowed_salt_dunders:
                    raise RuntimeError(
                        "Don't know how to handle {!r}. Passed loader module dict: {}".format(
                            key,
                            self.setup_loader_modules,
                        )
                    )
                elif key in salt_dunder_dicts and not hasattr(module, key):
                    # Add the key as a dictionary attribute to the module so it can be patched by `patch.dict`'
                    setattr(module, key, {})
                    # Remove the added attribute after the test finishes
                    self.addfinalizer(delattr, module, key)

            if not hasattr(module, key):
                # Set the key as an attribute so it can be patched
                setattr(module, key, None)
                # Remove the added attribute after the test finishes
                self.addfinalizer(delattr, module, key)
            module_globals[key] = mocks[key]

        # Patch the module!
        log.trace("Patching globals for %s; globals: %s", module, module_globals)
        patcher = patch.multiple(module, **module_globals)
        patcher.start()
        self.addfinalizer(patcher.stop)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
