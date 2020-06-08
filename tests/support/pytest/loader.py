# -*- coding: utf-8 -*-
"""
    tests.support.pytest.loader
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Salt's Loader PyTest Mock Support
"""
import functools
import logging
import sys
import types

import attr  # pylint: disable=3rd-party-module-not-gated
import salt.utils.functools
from tests.support.mock import patch

log = logging.getLogger(__name__)


@attr.s(init=True, slots=True, frozen=True)
class LoaderModuleMock:

    request = attr.ib(init=True)
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

    def __enter__(self):
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
                        if isinstance(mock_data, types.FunctionType):
                            mock_data = salt.utils.functools.namespaced_function(
                                mock_data, module_globals, preserve_context=True
                            )
                        module_globals.setdefault(key, {})[mock_key] = mock_data
                else:
                    if not hasattr(module, key):
                        # Set the key name as an attribute on the module if not present
                        setattr(module, key, None)
                        # Remove the added attribute after the test finishes
                        self.addfinalizer(delattr, module, key)
                    if isinstance(mocked_details, types.FunctionType):
                        mocked_details = salt.utils.functools.namespaced_function(
                            mocked_details, module_globals, preserve_context=True
                        )
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
        return self

    def __exit__(self, *args):
        pass

    def addfinalizer(self, func, *args, **kwargs):
        # Compat layer while we still support running the test suite under unittest
        try:
            self.request.addfinalizer(functools.partial(func, *args, **kwargs))
        except AttributeError:
            self.request.addCleanup(func, *args, **kwargs)
