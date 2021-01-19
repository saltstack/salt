import logging
import shutil

import pytest
import salt.features
import salt.loader
import salt.pillar

log = logging.getLogger(__name__)


class Loaders:
    def __init__(self, opts):
        self.opts = opts
        self.context = {}
        self._reset_state_funcs = [self.context.clear]
        self._grains = self._utils = self._modules = self._pillar = None
        self.opts["grains"] = self.grains
        self.refresh_pillar()
        salt.features.setup_features(self.opts)

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

    @property
    def pillar(self):
        if self._pillar is None:
            self._pillar = salt.pillar.get_pillar(
                self.opts,
                self.opts["grains"],
                self.opts["id"],
                saltenv=self.opts["saltenv"],
                pillarenv=self.opts.get("pillarenv"),
            ).compile_pillar()
        return self._pillar

    def refresh_pillar(self):
        self._pillar = None
        self.opts["pillar"] = self.pillar


@pytest.fixture(scope="package")
def minion_id():
    return "func-tests-minion"


@pytest.fixture(scope="module")
def state_tree(tmp_path_factory):
    state_tree_path = tmp_path_factory.mktemp("state-tree-base")
    try:
        yield state_tree_path
    finally:
        shutil.rmtree(str(state_tree_path), ignore_errors=True)


@pytest.fixture(scope="module")
def state_tree_prod(tmp_path_factory):
    state_tree_path = tmp_path_factory.mktemp("state-tree-prod")
    try:
        yield state_tree_path
    finally:
        shutil.rmtree(str(state_tree_path), ignore_errors=True)


@pytest.fixture(scope="module")
def minion_opts(
    salt_factories, minion_id, state_tree, state_tree_prod,
):
    config_overrides = {
        "file_client": "local",
        "file_roots": {"base": [str(state_tree)], "prod": [str(state_tree_prod)]},
        "features": {"enable_slsvars_fixes": True},
    }
    factory = salt_factories.get_salt_minion_daemon(
        minion_id, config_overrides=config_overrides,
    )
    return factory.config.copy()


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
