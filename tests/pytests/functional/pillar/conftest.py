import shutil

import pytest


@pytest.fixture(scope="package")
def pillar_state_tree(tmp_path_factory):
    _pillar_state_tree = tmp_path_factory.mktemp("pillar")
    try:
        yield _pillar_state_tree
    finally:
        shutil.rmtree(str(_pillar_state_tree), ignore_errors=True)


@pytest.fixture(scope="package")
def extension_modules(tmp_path_factory):
    _extension_modules = tmp_path_factory.mktemp("pillar")
    try:
        yield _extension_modules
    finally:
        shutil.rmtree(str(_extension_modules), ignore_errors=True)


@pytest.fixture(scope="package")
def salt_master(salt_factories, pillar_state_tree, extension_modules):
    config_defaults = {
        "pillar_roots": {"base": [str(pillar_state_tree)]},
        "open_mode": True,
        "extension_modules": str(extension_modules),
        "ext_pillar_first": False,
        "ext_pillar": [],
        "decrypt_pillar_default": "gpg",
        "decrypt_pillar_delimiter": ":",
        "decrypt_pillar_renderers": ["gpg"],
    }
    factory = salt_factories.get_salt_master_daemon(
        "pillar-functional-master", config_defaults=config_defaults
    )
    return factory


@pytest.fixture(scope="package")
def salt_minion_1(salt_master):
    factory = salt_master.get_salt_minion_daemon(
        "pillar-functional-minion-1", config_defaults={"open_mode": True}
    )
    return factory


@pytest.fixture(scope="package")
def salt_minion_2(salt_master):
    factory = salt_master.get_salt_minion_daemon(
        "pillar-functional-minion-2", config_defaults={"open_mode": True}
    )
    return factory
