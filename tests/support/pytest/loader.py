"""
    tests.support.pytest.loader
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Salt's Loader PyTest Mock Support
"""
import logging
import sys
import types
from collections import deque

import attr  # pylint: disable=3rd-party-module-not-gated
from tests.support.mock import patch

log = logging.getLogger(__name__)


@attr.s(init=True, slots=True, frozen=True)
class LoaderModuleMock:

    setup_loader_modules = attr.ib(init=True)
    salt_dunders = attr.ib(
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
            # Proxy is commented out on purpose since some code in salt expects a NameError
            # and is most of the time not a required dunder
            # '__proxy__'
        ),
    )
    _finalizers = attr.ib(
        init=False, repr=False, hash=False, default=attr.Factory(deque)
    )

    def start(self):
        module_globals = {dunder: {} for dunder in self.salt_dunders}
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
            for dunder in module_globals:
                if not hasattr(module, dunder):
                    # Set the dunder name as an attribute on the module if not present
                    setattr(module, dunder, {})
                    # Remove the added attribute after the test finishes
                    self.addfinalizer(delattr, module, dunder)
            for key in globals_to_mock:
                if key == "sys.modules":
                    sys_modules = globals_to_mock[key]
                    if not isinstance(sys_modules, dict):
                        raise RuntimeError(
                            "'sys.modules' must be a dictionary not: {}".format(
                                type(sys_modules)
                            )
                        )
                    patcher = patch.dict(sys.modules, sys_modules)
                    patcher.start()

                    def cleanup_sys_modules(patcher, sys_modules):
                        patcher.stop()
                        del patcher
                        del sys_modules

                    self.addfinalizer(cleanup_sys_modules, patcher, sys_modules)
                    continue

                mocked_details = globals_to_mock[key]
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
            log.trace(
                "Patching loader globals for %s; globals: %s", module, module_globals
            )
            patcher = patch.multiple(module, **module_globals)
            patcher.start()

            def cleanup_module_globals(patcher, module_globals):
                patcher.stop()
                del patcher
                module_globals.clear()
                del module_globals

            # Be sure to unpatch the module once the test finishes
            self.addfinalizer(cleanup_module_globals, patcher, module_globals)

    def stop(self):
        while self._finalizers:
            func, args, kwargs = self._finalizers.popleft()
            try:
                func(*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                log.error(
                    "Failed to run finalizer %s: %s",
                    self._format_callback(func, args, kwargs),
                    exc,
                    exc_info=True,
                )

    def addfinalizer(self, func, *args, **kwargs):
        """
        Register a function to run when stopping
        """
        self._finalizers.append((func, args, kwargs))

    def _format_callback(self, callback, args, kwargs):
        callback_str = "{}(".format(callback.__name__)
        if args:
            callback_str += ", ".join([repr(arg) for arg in args])
        if kwargs:
            callback_str += ", ".join(
                ["{}={!r}".format(k, v) for (k, v) in kwargs.items()]
            )
        callback_str += ")"
        return callback_str

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
