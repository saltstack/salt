import logging
import shutil

import pytest
from saltfactories.utils.functional import Loaders

log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def minion_id():
    return "func-tests-minion-opts"


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
def minion_config_defaults():
    """
    Functional test modules can provide this fixture to tweak the default configuration dictionary
    passed to the minion factory
    """
    return {}


@pytest.fixture(scope="module")
def minion_config_overrides():
    """
    Functional test modules can provide this fixture to tweak the configuration
    overrides dictionary passed to the minion factory
    """
    return {}


@pytest.fixture(scope="module")
def minion_opts(
    salt_factories,
    minion_id,
    state_tree,
    state_tree_prod,
    minion_config_defaults,
    minion_config_overrides,
):
    minion_config_overrides.update(
        {
            "file_client": "local",
            "file_roots": {
                "base": [
                    str(state_tree),
                ],
                "prod": [
                    str(state_tree_prod),
                ],
            },
        }
    )
    factory = salt_factories.salt_minion_daemon(
        minion_id,
        defaults=minion_config_defaults or None,
        overrides=minion_config_overrides,
    )
    return factory.config.copy()


@pytest.fixture(scope="module")
def master_config_defaults():
    """
    Functional test modules can provide this fixture to tweak the default configuration dictionary
    passed to the master factory
    """
    return {}


@pytest.fixture(scope="module")
def master_config_overrides():
    """
    Functional test modules can provide this fixture to tweak the configuration
    overrides dictionary passed to the master factory
    """
    return {}


@pytest.fixture(scope="module")
def master_opts(
    salt_factories,
    state_tree,
    state_tree_prod,
    master_config_defaults,
    master_config_overrides,
):
    master_config_overrides.update(
        {
            "file_client": "local",
            "file_roots": {
                "base": [
                    str(state_tree),
                ],
                "prod": [
                    str(state_tree_prod),
                ],
            },
        }
    )
    factory = salt_factories.salt_master_daemon(
        "func-tests-master-opts",
        defaults=master_config_defaults or None,
        overrides=master_config_overrides,
    )
    return factory.config.copy()


@pytest.fixture(scope="module")
def loaders(minion_opts):
    return Loaders(minion_opts, loaded_base_name=f"{__name__}.loaded")


@pytest.fixture(autouse=True)
def reset_loaders_state(loaders):
    try:
        # Run the tests
        yield
    finally:
        # Reset the loaders state
        loaders.reset_state()
