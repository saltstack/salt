import logging
import pathlib
import shutil

import pytest
from saltfactories.utils.functional import Loaders

log = logging.getLogger(__name__)


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
    state_tree_prod,
    minion_config_defaults,
    minion_config_overrides,
):
    minion_config_overrides.update(
        {
            "file_client": "local",
            "file_roots": {"base": [str(state_tree)], "prod": [str(state_tree_prod)]},
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
    # Delete the files cache after each test
    cachedir = pathlib.Path(loaders.opts["cachedir"])
    shutil.rmtree(str(cachedir), ignore_errors=True)
    cachedir.mkdir(parents=True, exist_ok=True)
    # The above can be deleted after pytest-salt-factories>=1.0.0rc7 has been merged
    try:
        # Run the tests
        yield
    finally:
        # Reset the loaders state
        loaders.reset_state()
