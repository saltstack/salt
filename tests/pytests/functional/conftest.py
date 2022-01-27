import logging
import shutil

import pytest
from saltfactories.utils.functional import Loaders
from saltfactories.utils.tempfiles import SaltStateTree

log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def minion_id():
    return "func-tests-minion"


@pytest.fixture(scope="session")
def state_tree(tmp_path_factory):
    state_tree_path = tmp_path_factory.mktemp("state-tree")
    state_tree_path.mkdir(exist_ok=True)
    base_state_tree_path = state_tree_path / "base"
    base_state_tree_path.mkdir(exist_ok=True)
    prod_state_tree_path = state_tree_path / "prod"
    prod_state_tree_path.mkdir(exist_ok=True)
    envs = {
        "base": [str(base_state_tree_path)],
        "prod": [str(prod_state_tree_path)],
    }
    try:
        yield SaltStateTree(envs=envs)
    finally:
        shutil.rmtree(str(state_tree_path), ignore_errors=True)


@pytest.fixture(scope="module")
def minion_config_defaults():
    """
    Functional test modules can provide this fixture to tweak the default configuration dictionary
    passed to the minion factory
    """
    return {}


@pytest.fixture(scope="module")
def minion_config_overrides():
    """
    Functional test modules can provide this fixture to tweak the configuration overrides dictionary
    passed to the minion factory
    """
    return {}


@pytest.fixture(scope="module")
def minion_opts(
    salt_factories,
    minion_id,
    state_tree,
    minion_config_defaults,
    minion_config_overrides,
):
    minion_config_overrides.update(
        {
            "file_client": "local",
            "file_roots": state_tree.as_dict(),
            "features": {"enable_slsvars_fixes": True},
        }
    )
    factory = salt_factories.salt_minion_daemon(
        minion_id,
        defaults=minion_config_defaults or None,
        overrides=minion_config_overrides,
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
