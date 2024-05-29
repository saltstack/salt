import shutil

import pytest

from tests.conftest import FIPS_TESTRUN


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
    config_overrides = {
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        "pillar-cache-functional-master",
        defaults=config_defaults,
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="package")
def pillar_salt_minion(pillar_salt_master):
    assert pillar_salt_master.is_running()
    config_overrides = {
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = pillar_salt_master.salt_minion_daemon(
        "pillar-cache-functional-minion-1",
        defaults={"open_mode": True, "hi": "there", "pass_to_ext_pillars": ["hi"]},
        overrides=config_overrides,
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
