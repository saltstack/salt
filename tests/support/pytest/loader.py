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
from salt.loader import LazyLoader
from tests.support.mock import patch

log = logging.getLogger(__name__)


@attr.s(init=True, slots=True, frozen=True)
class LoaderModuleMock:

    setup_loader_modules = attr.ib(init=True)
    # These dunders should always exist at the module global scope
    salt_module_dunders = attr.ib(
        init=True, repr=False, kw_only=True, default=("__opts__",),
    )
    # These dunders might exist at the module global scope
    salt_module_dunders_optional = attr.ib(
        init=True, repr=False, kw_only=True, default=("__proxyenabled__",),
    )
    # These dunders should always exist at the function global scope
    salt_function_dunders = attr.ib(
        init=True,
        repr=False,
        kw_only=True,
        default=(
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
    # These dunders might exist at the function global scope
    salt_function_dunders_optional = attr.ib(
        init=True, repr=False, kw_only=True, default=("__proxy__",),
    )
    # These dunders might exist at the function global scope
    salt_function_dunder_attributes = attr.ib(
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
        ),
    )
    _finalizers = attr.ib(
        init=False, repr=False, hash=False, default=attr.Factory(deque)
    )

    def start(self):
        module_globals = {dunder: {} for dunder in self.salt_module_dunders}
        function_globals = {dunder: {} for dunder in self.salt_function_dunders}
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
            for key in module_globals:
                if not hasattr(module, key):
                    # Set the dunder name as an attribute on the module if not present
                    setattr(module, key, {})
                    # Remove the added attribute after the test finishes
                    self.addfinalizer(delattr, module, key)
            # Patch sys.modules as the first step
            self._patch_sys_modules(globals_to_mock)
            # Now we need to first patch the function globals because the salt loader
            # only loads functions and if the module globals patch a function, that
            # function won't be loaded.
            #
            # So, first we patch the function globals
            self._patch_function_globals(module, globals_to_mock, function_globals)
            # And now we can patch the module globals
            self._patch_module_globals(module, globals_to_mock, module_globals)

    def stop(self):
        while self._finalizers:
            func, args, kwargs = self._finalizers.popleft()
            func_repr = self._format_callback(func, args, kwargs)
            try:
                log.trace("Calling finalizer %s", func_repr)
                func(*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                log.error(
                    "Failed to run finalizer %s: %s", func_repr, exc, exc_info=True,
                )

    def addfinalizer(self, func, *args, **kwargs):
        """
        Register a function to run when stopping
        """
        self._finalizers.append((func, args, kwargs))

    def _format_callback(self, callback, args, kwargs):
        callback_str = "{}(".format(callback.__qualname__)
        if args:
            callback_str += ", ".join([repr(arg) for arg in args])
        if kwargs:
            callback_str += ", ".join(
                ["{}={!r}".format(k, v) for (k, v) in kwargs.items()]
            )
        callback_str += ")"
        return callback_str

    def _patch_sys_modules(self, mocks):
        if "sys.modules" not in mocks:
            return
        sys_modules = mocks["sys.modules"]
        if not isinstance(sys_modules, dict):
            raise RuntimeError(
                "'sys.modules' must be a dictionary not: {}".format(type(sys_modules))
            )
        patcher = patch.dict(sys.modules, values=sys_modules)
        patcher.start()
        self.addfinalizer(patcher.stop)

    def _patch_module_globals(self, module, mocks, module_globals):
        module_globals_skip_keys = (
            (
                # sys.modules is addressed on another function
                "sys.modules",
            )
            # Salt function globals are addressed on another function
            + self.salt_function_dunders
            + self.salt_function_dunders_optional
            + self.salt_function_dunder_attributes
        )
        for key in mocks:
            if key in module_globals_skip_keys:
                continue

            mocked_details = mocks[key]
            if isinstance(mocked_details, dict) and key.startswith("__"):
                # A salt dunder
                if not hasattr(module, key):
                    # Set the dunder name as an attribute on the module if not present
                    setattr(module, key, {})
                    # Remove the added attribute after the test finishes
                    self.addfinalizer(delattr, module, key)
                for mock_key, mock_data in mocked_details.items():
                    module_globals.setdefault(key, {})[mock_key] = mock_data
            else:
                if not hasattr(module, key):
                    # Set the key name as an attribute on the module if not present
                    setattr(module, key, None)
                    # Remove the added attribute after the test finishes
                    self.addfinalizer(delattr, module, key)
                module_globals[key] = mocked_details

        # Patch the module!
        log.trace("Patching globals for %s; globals: %s", module, module_globals)
        patcher = patch.multiple(module, **module_globals)
        patcher.start()
        self.addfinalizer(patcher.stop)

    def _patch_function_globals(self, module, mocks, function_globals):
        function_globals_skip_keys = (
            (
                # sys.modules is addressed on another function
                "sys.modules",
            )
            # Module globals are adressed on another function
            + self.salt_module_dunders
            + self.salt_module_dunders_optional
        )
        for key in mocks:
            if key in function_globals_skip_keys:
                continue

            if not key.startswith("__"):
                # We only patch salt dunders in function globals
                continue

            if (
                key
                not in self.salt_function_dunders
                + self.salt_function_dunders_optional
                + self.salt_function_dunder_attributes
            ):
                raise RuntimeError(
                    "Don't know how to handle {!r}. Passed loader module dict: {}".format(
                        key, self.setup_loader_modules,
                    )
                )

            mocked_details = mocks[key]
            if not isinstance(mocked_details, dict):
                function_globals[key] = mocked_details
                continue

            # If we get passed an empty mocked_details dictionary, we need to at least
            # add that key to the function globals
            function_globals.setdefault(key, {})

            for mock_key, mock_data in mocked_details.items():
                function_globals[key][mock_key] = mock_data

        for name, alias, func in LazyLoader.loadable_attributes(module):
            if func.__module__ != module.__name__:
                # Don't patch imported functions.
                # XXX: This should actually be the default loader behavior
                continue
            if hasattr(func, "__wrapped__"):
                log.trace(
                    "%s is a decorated function. Searching for the undecorated function",
                    func,
                )
                while True:
                    try:
                        func = func.__wrapped__
                    except AttributeError:
                        break
            # Patch each LazyLoader loadable attribute!
            log.trace("Patching globals for %s; globals: %s", func, function_globals)
            patcher = patch.dict(func.__globals__, values=function_globals)
            patcher.start()
            self.addfinalizer(patcher.stop)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
