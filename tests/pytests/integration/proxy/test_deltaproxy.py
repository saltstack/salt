"""
Simple Smoke Tests for Connected Proxy Minion
"""

import logging

import pytest

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_on_spawning_platform(
        reason="Deltaproxy minions do not currently work on spawning platforms.",
    ),
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def skip_on_tcp_transport(request):
    if request.config.getoption("--transport") == "tcp":
        pytest.skip("Deltaproxy under the TPC transport is not working. See #61367")


@pytest.fixture(params=pytest.helpers.proxy.delta_proxy_minion_ids())
def proxy_id(request, salt_delta_proxy, skip_on_tcp_transport):
    return request.param


@pytest.fixture
def proxy_ids(request, salt_delta_proxy, skip_on_tcp_transport):
    return pytest.helpers.proxy.delta_proxy_minion_ids()


def test_can_it_ping(salt_cli, proxy_id, proxy_ids):
    """
    Ensure the proxy can ping
    """
    ret = salt_cli.run("test.ping", minion_tgt=proxy_id)
    assert ret.data is True


def test_can_it_ping_all(salt_cli, proxy_ids):
    """
    Ensure the proxy can ping (all proxy minions)
    """
    ret = salt_cli.run("-L", "test.ping", minion_tgt=",".join(proxy_ids))
    for _id in proxy_ids:
        assert ret.data[_id] is True


def test_list_pkgs(salt_cli, proxy_id):
    """
    Package test 1, really just tests that the virtual function capability
    is working OK.
    """
    ret = salt_cli.run("pkg.list_pkgs", minion_tgt=proxy_id)
    assert "coreutils" in ret.data
    assert "apache" in ret.data
    assert "redbull" in ret.data


def test_list_pkgs_all(salt_cli, proxy_ids):
    """
    Ensure the proxy can ping (all proxy minions)
    """
    pkg_list = {"apache": "2.4", "coreutils": "1.0", "redbull": "999.99", "tinc": "1.4"}
    ret = salt_cli.run("-L", "pkg.list_pkgs", minion_tgt=",".join(proxy_ids))
    for _id in proxy_ids:
        assert ret.data[_id] == pkg_list


def test_install_pkgs(salt_cli, proxy_id):
    """
    Package test 2, really just tests that the virtual function capability
    is working OK.
    """

    ret = salt_cli.run("pkg.install", "thispkg", minion_tgt=proxy_id)
    assert ret.data["thispkg"] == "1.0"

    ret = salt_cli.run("pkg.list_pkgs", minion_tgt=proxy_id)

    assert ret.data["apache"] == "2.4"
    assert ret.data["redbull"] == "999.99"
    assert ret.data["thispkg"] == "1.0"


def test_install_pkgs_all(salt_cli, proxy_ids):
    """
    Ensure the proxy can ping (all proxy minions)
    """
    install_ret = salt_cli.run(
        "-L", "pkg.install", "thispkg", minion_tgt=",".join(proxy_ids)
    )
    list_ret = salt_cli.run("-L", "pkg.list_pkgs", minion_tgt=",".join(proxy_ids))

    for _id in proxy_ids:

        assert install_ret.data[_id]["thispkg"] == "1.0"

        assert list_ret.data[_id]["apache"] == "2.4"
        assert list_ret.data[_id]["redbull"] == "999.99"
        assert list_ret.data[_id]["thispkg"] == "1.0"


def test_remove_pkgs(salt_cli, proxy_id):
    ret = salt_cli.run("pkg.remove", "apache", minion_tgt=proxy_id)
    assert "apache" not in ret.data

    # reinstall
    ret = salt_cli.run("pkg.install", "apache", minion_tgt=proxy_id)


def test_remove_pkgs_all(salt_cli, proxy_ids):
    """
    Ensure the proxy can ping (all proxy minions)
    """
    ret = salt_cli.run("-L", "pkg.remove", "coreutils", minion_tgt=",".join(proxy_ids))

    for _id in proxy_ids:
        assert "coreutils" not in ret.data[_id]

    # reinstall
    salt_cli.run("-L", "pkg.install", "coreutils", minion_tgt=",".join(proxy_ids))


def test_upgrade(salt_cli, proxy_id):
    ret = salt_cli.run("pkg.upgrade", minion_tgt=proxy_id)
    assert ret.data["coreutils"]["new"] == "2.0"
    assert ret.data["redbull"]["new"] == "1000.99"


def test_service_list(salt_cli, proxy_id):
    ret = salt_cli.run("service.list", minion_tgt=proxy_id)
    assert "ntp" in ret.data


def test_service_stop(salt_cli, proxy_id):
    ret = salt_cli.run("service.stop", "ntp", minion_tgt=proxy_id)
    ret = salt_cli.run("service.status", "ntp", minion_tgt=proxy_id)
    assert ret.data is False


def test_service_start(salt_cli, proxy_id):
    ret = salt_cli.run("service.start", "samba", minion_tgt=proxy_id)
    ret = salt_cli.run("service.status", "samba", minion_tgt=proxy_id)
    assert ret.data is True


def test_service_get_all(salt_cli, proxy_id):
    ret = salt_cli.run("service.get_all", minion_tgt=proxy_id)
    assert ret.data
    assert "samba" in ret.data


def test_grains_items(salt_cli, proxy_id):
    ret = salt_cli.run("grains.items", minion_tgt=proxy_id)
    assert ret.data["kernel"] == "proxy"
    assert ret.data["kernelrelease"] == "proxy"


def test_state_apply(salt_master, salt_cli, tmp_path, proxy_id):
    test_file = tmp_path / "testfile"
    core_state = """
    {}:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
        """.format(
        test_file
    )

    with salt_master.state_tree.base.temp_file("core.sls", core_state):
        ret = salt_cli.run("state.apply", "core", minion_tgt=proxy_id)
        for value in ret.data.values():
            assert value["result"] is True


@pytest.mark.slow_test
def test_state_highstate(salt_master, salt_cli, tmp_path, proxy_id):
    test_file = tmp_path / "testfile"
    top_sls = """
    base:
      '*':
        - core
        """

    core_state = """
    {}:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
        """.format(
        test_file
    )

    with salt_master.state_tree.base.temp_file(
        "top.sls", top_sls
    ), salt_master.state_tree.base.temp_file("core.sls", core_state):
        ret = salt_cli.run("state.highstate", minion_tgt=proxy_id)
        for value in ret.data.values():
            assert value["result"] is True


def test_config_get(salt_cli, proxy_id):
    """
    Ensure the config module returns the right id
    when targeting deltaproxy managed proxy minions.
    """
    ret = salt_cli.run("config.get", "id", minion_tgt=proxy_id)
    assert ret.data == proxy_id


def test_schedule_list(salt_cli, proxy_id):
    """
    Ensure schedule.list works
    """
    ret = salt_cli.run("schedule.list", minion_tgt=proxy_id)
    assert ret.data == "schedule: {}\n"


def test_schedule_add_list(salt_cli, proxy_id):
    """
    Ensure schedule.add works
    """
    ret = salt_cli.run(
        "schedule.add", name="job1", function="test.ping", minion_tgt=proxy_id
    )
    assert "result" in ret.data
    assert ret.data["result"]

    assert "comment" in ret.data
    assert ret.data["comment"] == "Added job: job1 to schedule."

    assert "changes" in ret.data
    assert ret.data["changes"] == {"job1": "added"}

    _expected = """schedule:
  job1:
    enabled: true
    function: test.ping
    jid_include: true
    maxrunning: 1
    name: job1
    saved: true
"""
    ret = salt_cli.run("schedule.list", minion_tgt=proxy_id)
    assert ret.data == _expected

    # clean out the scheduler
    salt_cli.run("schedule.purge", minion_tgt=proxy_id)


def test_schedule_add_list_all(salt_cli, proxy_ids):
    """
    Ensure schedule.add works when targeting a single minion
    and that the others are not affected.
    """
    ret = salt_cli.run(
        "schedule.add", name="job2", function="test.ping", minion_tgt=proxy_ids[0]
    )
    assert "result" in ret.data
    assert ret.data["result"]

    ret = salt_cli.run("-L", "schedule.list", minion_tgt=",".join(proxy_ids))

    # check every proxy except the first one
    for _id in proxy_ids[1:]:
        assert ret.data[_id] == "schedule: {}\n"

    # clean out the scheduler
    salt_cli.run("-L", "schedule.purge", minion_tgt=",".join(proxy_ids))
