"""
Integration tests for the saltutil module.
"""

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(autouse=True)
def refresh_pillar(salt_call_cli, salt_minion, salt_sub_minion):
    whitelist = {
        "modules": [],
    }
    ret = salt_call_cli.run("saltutil.sync_all", extmod_whitelist=whitelist)
    assert ret.returncode == 0
    assert ret.data
    try:
        yield
    finally:
        ret = salt_call_cli.run("saltutil.sync_all")
        assert ret.returncode == 0
        assert ret.data


@pytest.mark.slow_test
def test_sync_all(salt_call_cli):
    """
    Test syncing all ModuleCase
    """
    expected_return = {
        "engines": [],
        "clouds": [],
        "grains": [],
        "beacons": [],
        "utils": [],
        "returners": [],
        "modules": [
            "modules.depends_versioned",
            "modules.depends_versionless",
            "modules.override_test",
            "modules.runtests_decorators",
            "modules.runtests_helpers",
            "modules.salttest",
        ],
        "renderers": [],
        "log_handlers": [],
        "matchers": [],
        "states": [],
        "sdb": [],
        "proxymodules": [],
        "executors": [],
        "output": [],
        "thorium": [],
        "serializers": [],
    }
    ret = salt_call_cli.run("saltutil.sync_all")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == expected_return


@pytest.mark.slow_test
def test_sync_all_whitelist(salt_call_cli):
    """
    Test syncing all ModuleCase with whitelist
    """
    expected_return = {
        "engines": [],
        "clouds": [],
        "grains": [],
        "beacons": [],
        "utils": [],
        "returners": [],
        "modules": ["modules.salttest"],
        "renderers": [],
        "log_handlers": [],
        "matchers": [],
        "states": [],
        "sdb": [],
        "proxymodules": [],
        "executors": [],
        "output": [],
        "thorium": [],
        "serializers": [],
    }
    ret = salt_call_cli.run(
        "saltutil.sync_all", extmod_whitelist={"modules": ["salttest"]}
    )
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == expected_return


@pytest.mark.slow_test
def test_sync_all_blacklist(salt_call_cli):
    """
    Test syncing all ModuleCase with blacklist
    """
    expected_return = {
        "engines": [],
        "clouds": [],
        "grains": [],
        "beacons": [],
        "utils": [],
        "returners": [],
        "modules": [
            "modules.override_test",
            "modules.runtests_helpers",
            "modules.salttest",
        ],
        "renderers": [],
        "log_handlers": [],
        "matchers": [],
        "states": [],
        "sdb": [],
        "proxymodules": [],
        "executors": [],
        "output": [],
        "thorium": [],
        "serializers": [],
    }
    ret = salt_call_cli.run(
        "saltutil.sync_all",
        extmod_blacklist={
            "modules": [
                "runtests_decorators",
                "depends_versioned",
                "depends_versionless",
            ]
        },
    )
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == expected_return


@pytest.mark.slow_test
def test_sync_all_blacklist_and_whitelist(salt_call_cli):
    """
    Test syncing all ModuleCase with whitelist and blacklist
    """
    expected_return = {
        "engines": [],
        "clouds": [],
        "grains": [],
        "beacons": [],
        "utils": [],
        "returners": [],
        "executors": [],
        "modules": [],
        "renderers": [],
        "log_handlers": [],
        "matchers": [],
        "states": [],
        "sdb": [],
        "proxymodules": [],
        "output": [],
        "thorium": [],
        "serializers": [],
    }
    ret = salt_call_cli.run(
        "saltutil.sync_all",
        extmod_whitelist={"modules": ["runtests_decorators"]},
        extmod_blacklist={"modules": ["runtests_decorators"]},
    )
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == expected_return
