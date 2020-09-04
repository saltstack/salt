import pytest


@pytest.fixture(scope="package")
def salt_master(request, salt_factories, salt_master_config):
    return salt_factories.spawn_master(request, "master")


@pytest.fixture(scope="package")
def salt_minion(request, salt_factories, salt_master, salt_minion_config):
    proc = salt_factories.spawn_minion(request, "minion", master_id="master")
    # Sync All
    salt_call_cli = salt_factories.get_salt_call_cli("minion")
    ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
    assert ret.exitcode == 0, ret
    return proc


@pytest.fixture(scope="package")
def salt_sub_minion(request, salt_factories, salt_master, salt_sub_minion_config):
    proc = salt_factories.spawn_minion(request, "sub_minion", master_id="master")
    # Sync All
    salt_call_cli = salt_factories.get_salt_call_cli("sub_minion")
    ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
    assert ret.exitcode == 0, ret
    return proc


@pytest.fixture(scope="package")
def salt_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_cli(salt_master.config["id"])


@pytest.fixture(scope="package")
def salt_cp_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_cp_cli(salt_master.config["id"])


@pytest.fixture(scope="package")
def salt_key_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_key_cli(salt_master.config["id"])


@pytest.fixture(scope="package")
def salt_run_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_run_cli(salt_master.config["id"])


@pytest.fixture(scope="package")
def salt_call_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_call_cli(salt_minion.config["id"])
