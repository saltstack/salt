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
def pillar_salt_master(salt_factories, pillar_state_tree):
    config_defaults = {
        "pillar_roots": {"base": [str(pillar_state_tree)]},
        "open_mode": True,
        "pillar_cache": True,
        "ext_pillar": [
            {"extra_minion_data_in_pillar": "*"},
        ],
    }
    factory = salt_factories.salt_master_daemon(
        "pillar-cache-functional-master", defaults=config_defaults
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="package")
def pillar_salt_minion(pillar_salt_master):
    assert pillar_salt_master.is_running()
    factory = pillar_salt_master.salt_minion_daemon(
        "pillar-cache-functional-minion-1",
        defaults={"open_mode": True, "hi": "there", "pass_to_ext_pillars": ["hi"]},
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.fixture(scope="package")
def pillar_salt_call_cli(pillar_salt_minion):
    return pillar_salt_minion.salt_call_cli()
