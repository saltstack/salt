import logging
import shutil

import pytest
import salt.loader

log = logging.getLogger(__name__)


class Loaders:
    def __init__(self, opts):
        self.opts = opts
        self.context = {}
        self._reset_state_funcs = [self.context.clear]
        # Sadly, we can't use cached_property until Py3.6, and this is using a backports package
        self._grains = self._utils = self._modules = None
        self.opts["grains"] = self.grains

    def reset_state(self):
        for func in self._reset_state_funcs:
            func()

    @property
    def grains(self):
        if self._grains is None:
            self._grains = salt.loader.grains(self.opts, context=self.context)
        return self._grains

    @property
    def utils(self):
        if self._utils is None:
            self._utils = salt.loader.utils(self.opts, context=self.context)
        return self._utils

    @property
    def modules(self):
        if self._modules is None:
            self._modules = salt.loader.minion_mods(
                self.opts, context=self.context, utils=self.utils, initial_load=True
            )
        return self._modules


@pytest.fixture(scope="module")
def state_tree_base(tmp_path_factory):
    state_tree_path = tmp_path_factory.mktemp("state-tree-base")
    try:
        yield state_tree_path
    finally:
        shutil.rmtree(str(state_tree_path), ignore_errors=True)


@pytest.fixture(scope="module")
def state_tree(tmp_path_factory):
    state_tree_path = tmp_path_factory.mktemp("state-tree-overrides")
    try:
        yield state_tree_path
    finally:
        shutil.rmtree(str(state_tree_path), ignore_errors=True)


@pytest.fixture(scope="module")
def minion_opts(salt_factories, state_tree_base, state_tree):
    config_overrides = {
        "file_client": "local",
        "file_roots": {"base": [str(state_tree), str(state_tree_base)]},
    }
    factory = salt_factories.get_salt_minion_daemon(
        "functional-tests-minion", config_overrides=config_overrides,
    )
    opts = factory.config.copy()
    # opts["grains"] =
    return opts


@pytest.fixture(scope="module")
def loaders(minion_opts):
    return Loaders(minion_opts)


@pytest.fixture(autouse=True)
def reset_loaders_state(loaders):
    try:
        # Run the tests
        yield
    finally:
        # Reset the loaders state
        loaders.reset_state()
