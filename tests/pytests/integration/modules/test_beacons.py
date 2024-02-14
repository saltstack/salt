"""
    :codeauthor: Justin Anderson <janderson@saltstack.com>
"""
import pathlib
import shutil

import attr
import pytest

from tests.support.helpers import PRE_PYTEST_SKIP_OR_NOT

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
    pytest.mark.timeout_unless_on_windows(200),
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
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["result"] is True
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
        assert ret.returncode == 0
        assert ret.data
        assert ret.data["result"] is True


@pytest.fixture(scope="module")
def inotify_file_path(tmp_path_factory):
    inotify_directory = tmp_path_factory.mktemp("important-files")
    try:
        yield inotify_directory / "really-important"
    finally:
        shutil.rmtree(str(inotify_directory), ignore_errors=True)


@pytest.fixture(scope="module")
def pillar_tree(
    base_env_pillar_tree_root_dir, salt_minion, salt_call_cli, inotify_file_path
):
    top_file = """
    base:
      '{}':
        - beacons
    """.format(
        salt_minion.id
    )
    beacon_pillar_file = """
    beacons:
      inotify:
        - files:
            {}:
              mask:
                - open
                - create
                - close_write
    """.format(
        inotify_file_path
    )
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    beacon_tempfile = pytest.helpers.temp_file(
        "beacons.sls", beacon_pillar_file, base_env_pillar_tree_root_dir
    )
    try:
        with top_tempfile, beacon_tempfile:
            ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
            assert ret.returncode == 0
            assert ret.data is True
            yield
    finally:
        # Refresh pillar again to cleaup the temp pillar
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True


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
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["result"] is True

    # Save beacons
    ret = salt_call_cli.run("beacons.save")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["result"] is True

    # Delete beacon
    ret = salt_call_cli.run("beacons.delete", beacon_instance.name)
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["result"] is True


@pytest.fixture
def beacon(beacon_instance, salt_call_cli):
    ret = salt_call_cli.run(
        "beacons.add", beacon_instance.name, beacon_data=beacon_instance.data
    )
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["result"] is True

    # Save beacons
    ret = salt_call_cli.run("beacons.save")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["result"] is True

    # assert beacon exists
    ret = salt_call_cli.run("beacons.list", return_yaml=False)
    assert ret.returncode == 0
    assert ret.data
    assert beacon_instance.name in ret.data

    yield beacon_instance


def test_disable(salt_call_cli, beacon):
    """
    Test disabling beacons
    """
    ret = salt_call_cli.run("beacons.disable")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["result"] is True

    # assert beacons are disabled
    ret = salt_call_cli.run("beacons.list", return_yaml=False)
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["enabled"] is False

    # disable added beacon
    ret = salt_call_cli.run("beacons.disable_beacon", beacon.name)
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["result"] is True

    # assert beacon is disabled
    ret = salt_call_cli.run("beacons.list", return_yaml=False)
    assert ret.returncode == 0
    assert ret.data
    assert beacon.name in ret.data
    for beacon_data in ret.data[beacon.name]:
        if "enabled" in beacon_data:
            assert beacon_data["enabled"] is False
            break
    else:
        pytest.fail("Did not find the beacon data with the 'enabled' key")


@pytest.fixture
def disabled_beacon(beacon, salt_call_cli):
    ret = salt_call_cli.run("beacons.disable")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["result"] is True
    return beacon


def test_enable(salt_call_cli, disabled_beacon):
    """
    Test enabling beacons
    """
    # enable beacons on minion
    ret = salt_call_cli.run("beacons.enable")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["result"] is True

    # assert beacons are enabled
    ret = salt_call_cli.run("beacons.list", return_yaml=False)
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["enabled"] is True


@pytest.mark.skipif(
    PRE_PYTEST_SKIP_OR_NOT,
    reason=(
        "Skip until https://github.com/saltstack/salt/issues/31516 problems are resolved."
    ),
)
def test_enabled_beacons(salt_call_cli, beacon):
    """
    Test enabled specific beacon
    """
    # enable added beacon
    ret = salt_call_cli.run("beacons.enable_beacon", beacon.name)
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["result"] is True

    # assert beacon ps is enabled
    ret = salt_call_cli.run("beacons.list", return_yaml=False)
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["enabled"] is True
    assert beacon.name in ret.data
    for beacon_data in ret.data[beacon.name]:
        if "enabled" in beacon_data:
            assert beacon_data["enabled"] is False
            break
    else:
        pytest.fail("Did not find the beacon data with the 'enabled' key")


@pytest.mark.usefixtures("pillar_tree")
def test_list(salt_call_cli, beacon, inotify_file_path):
    """
    Test listing the beacons
    """
    # list beacons
    ret = salt_call_cli.run("beacons.list", return_yaml=False)
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == {
        beacon.name: beacon.data,
        "inotify": [
            {
                "files": {
                    str(inotify_file_path): {"mask": ["open", "create", "close_write"]}
                }
            }
        ],
    }


@pytest.mark.usefixtures("pillar_tree")
def test_list_only_include_opts(salt_call_cli, beacon):
    """
    Test listing the beacons which only exist in opts

    When beacon.save is used to save the running beacons to
    a file, it uses beacons.list to get that list and should
    only return those from opts and not pillar.

    In this test, we're making sure we get only get back the
    beacons that are in opts and not those in pillar.
    """
    # list beacons
    ret = salt_call_cli.run(
        "beacons.list", return_yaml=False, include_opts=True, include_pillar=False
    )
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == {beacon.name: beacon.data}


@pytest.mark.usefixtures("pillar_tree", "beacon")
def test_list_only_include_pillar(salt_call_cli, inotify_file_path):
    """
    Test listing the beacons which only exist in pillar
    """
    # list beacons
    ret = salt_call_cli.run(
        "beacons.list", return_yaml=False, include_opts=False, include_pillar=True
    )
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == {
        "inotify": [
            {
                "files": {
                    str(inotify_file_path): {"mask": ["open", "create", "close_write"]}
                }
            }
        ]
    }


def test_list_available(salt_call_cli):
    """
    Test listing the beacons
    """
    # list beacons
    ret = salt_call_cli.run("beacons.list_available", return_yaml=False)
    assert ret.returncode == 0
    assert ret.data
    assert "ps" in ret.data
