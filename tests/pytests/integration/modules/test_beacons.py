"""
    :codeauthor: Justin Anderson <janderson@saltstack.com>
"""
import pathlib

import attr
import pytest
from tests.support.helpers import PRE_PYTEST_SKIP_OR_NOT

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


@attr.s(frozen=True, slots=True)
class SaltCallCliWrapper:
    salt_call_cli = attr.ib()

    def run(self, *args, **kwargs):
        beacon_event_timeout = 120
        cli_run_timeout = beacon_event_timeout + 30
        return self.salt_call_cli.run(
            *args, timeout=beacon_event_timeout, _timeout=cli_run_timeout, **kwargs
        )


@pytest.fixture(scope="module")
def salt_call_cli(salt_call_cli):
    return SaltCallCliWrapper(salt_call_cli)


@pytest.fixture(scope="module")
def cleanup_beacons_config_module(salt_minion, salt_call_cli):
    minion_conf_d_dir = (
        pathlib.Path(salt_minion.config_dir)
        / pathlib.Path(salt_minion.config["default_include"]).parent
    )
    if not minion_conf_d_dir.is_dir():
        minion_conf_d_dir.mkdir()
    beacons_config_file_path = minion_conf_d_dir / "beacons.conf"
    ret = salt_call_cli.run("beacons.reset")
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json["result"] is True
    if beacons_config_file_path.exists():
        beacons_config_file_path.unlink()
    try:
        yield beacons_config_file_path
    finally:
        if beacons_config_file_path.exists():
            beacons_config_file_path.unlink()


@pytest.fixture(autouse=True)
def cleanup_beacons_config(cleanup_beacons_config_module, salt_call_cli):
    try:
        yield cleanup_beacons_config_module
    finally:
        ret = salt_call_cli.run("beacons.reset")
        assert ret.exitcode == 0
        assert ret.json
        assert ret.json["result"] is True


@attr.s(frozen=True, slots=True)
class Beacon:
    name = attr.ib()
    data = attr.ib()


def beacon_instance_ids(value):
    return str(value)


@pytest.fixture(
    params=[
        Beacon("ps", [{"processes": {"apache2": "stopped"}}]),
        Beacon(
            "watch_apache",
            [{"processes": {"apache2": "stopped"}}, {"beacon_module": "ps"}],
        ),
    ],
    ids=beacon_instance_ids,
)
def beacon_instance(request):
    return request.param


def test_add_and_delete(salt_call_cli, beacon_instance):
    """
    Test adding and deleting a beacon
    """
    # Add the beacon
    ret = salt_call_cli.run(
        "beacons.add", beacon_instance.name, beacon_data=beacon_instance.data
    )
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json["result"] is True

    # Save beacons
    ret = salt_call_cli.run("beacons.save")
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json["result"] is True

    # Delete beacon
    ret = salt_call_cli.run("beacons.delete", beacon_instance.name)
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json["result"] is True


@pytest.fixture
def beacon(beacon_instance, salt_call_cli):
    ret = salt_call_cli.run(
        "beacons.add", beacon_instance.name, beacon_data=beacon_instance.data
    )
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json["result"] is True

    # Save beacons
    ret = salt_call_cli.run("beacons.save")
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json["result"] is True

    # assert beacon exists
    ret = salt_call_cli.run("beacons.list", return_yaml=False)
    assert ret.exitcode == 0
    assert ret.json
    assert beacon_instance.name in ret.json

    yield beacon_instance


def test_disable(salt_call_cli, beacon):
    """
    Test disabling beacons
    """
    ret = salt_call_cli.run("beacons.disable")
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json["result"] is True

    # assert beacons are disabled
    ret = salt_call_cli.run("beacons.list", return_yaml=False)
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json["enabled"] is False

    # disable added beacon
    ret = salt_call_cli.run("beacons.disable_beacon", beacon.name)
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json["result"] is True

    # assert beacon is disabled
    ret = salt_call_cli.run("beacons.list", return_yaml=False)
    assert ret.exitcode == 0
    assert ret.json
    assert beacon.name in ret.json
    for beacon_data in ret.json[beacon.name]:
        if "enabled" in beacon_data:
            assert beacon_data["enabled"] is False
            break
    else:
        pytest.fail("Did not find the beacon data with the 'enabled' key")


@pytest.fixture
def disabled_beacon(beacon, salt_call_cli):
    ret = salt_call_cli.run("beacons.disable")
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json["result"] is True
    return beacon


def test_enable(salt_call_cli, disabled_beacon):
    """
    Test enabling beacons
    """
    # enable beacons on minion
    ret = salt_call_cli.run("beacons.enable")
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json["result"] is True

    # assert beacons are enabled
    ret = salt_call_cli.run("beacons.list", return_yaml=False)
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json["enabled"] is True


@pytest.mark.skipif(
    PRE_PYTEST_SKIP_OR_NOT,
    reason="Skip until https://github.com/saltstack/salt/issues/31516 problems are resolved.",
)
def test_enabled_beacons(salt_call_cli, beacon):
    """
    Test enabled specific beacon
    """
    # enable added beacon
    ret = salt_call_cli.run("beacons.enable_beacon", beacon.name)
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json["result"] is True

    # assert beacon ps is enabled
    ret = salt_call_cli.run("beacons.list", return_yaml=False)
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json["enabled"] is True
    assert beacon.name in ret.json
    for beacon_data in ret.json[beacon.name]:
        if "enabled" in beacon_data:
            assert beacon_data["enabled"] is False
            break
    else:
        pytest.fail("Did not find the beacon data with the 'enabled' key")


def test_list(salt_call_cli, beacon):
    """
    Test listing the beacons
    """
    # list beacons
    ret = salt_call_cli.run("beacons.list", return_yaml=False)
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == {beacon.name: beacon.data}


def test_list_available(salt_call_cli):
    """
    Test listing the beacons
    """
    # list beacons
    ret = salt_call_cli.run("beacons.list_available", return_yaml=False)
    assert ret.exitcode == 0
    assert ret.json
    assert "ps" in ret.json
