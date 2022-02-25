"""
:codeauthor: Gareth J. Greenaway (ggreenaway@vmware.com)
"""

import logging
import os

import pytest
import salt.defaults.exitcodes
from saltfactories.exceptions import FactoryNotStarted
from saltfactories.utils import random_string
from tests.support.helpers import PRE_PYTEST_SKIP_REASON

log = logging.getLogger(__name__)


@pytest.fixture(scope="package", autouse=True)
def skip_on_tcp_transport(request):
    if request.config.getoption("--transport") == "tcp":
        pytest.skip("Deltaproxy under the TPC transport is not working. See #61367")


@pytest.fixture
def proxy_minion_id(salt_master):
    _proxy_minion_id = random_string("proxy-minion-")

    try:
        yield _proxy_minion_id
    finally:
        # Remove stale key if it exists
        pytest.helpers.remove_stale_minion_key(salt_master, _proxy_minion_id)


def clear_proxy_minions(salt_master, proxy_minion_id):
    for proxy in [
        proxy_minion_id,
        "dummy_proxy_one",
        "dummy_proxy_two",
        "broken_proxy_one",
        "broken_proxy_two",
    ]:
        pytest.helpers.remove_stale_minion_key(salt_master, proxy)

        cachefile = os.path.join(
            salt_master.config["cachedir"], "{}.cache".format(proxy)
        )
        if os.path.exists(cachefile):
            os.unlink(cachefile)


@pytest.mark.slow_test
def test_exit_status_no_proxyid(salt_master, proxy_minion_id):
    """
    Ensure correct exit status when --proxyid argument is missing.
    """
    config_defaults = {
        "metaproxy": "deltaproxy",
    }

    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id, include_proxyid_cli_flag=False, defaults=config_defaults
        )
        factory.start(start_timeout=10, max_start_attempts=1)

    assert exc.value.exitcode == salt.defaults.exitcodes.EX_USAGE, exc.value
    assert "Usage" in exc.value.stderr, exc.value
    assert "error: salt-proxy requires --proxyid" in exc.value.stderr, exc.value


@pytest.mark.skip_on_windows(reason="Windows does not do user checks")
def test_exit_status_unknown_user(salt_master, proxy_minion_id):
    """
    Ensure correct exit status when the proxy is configured to run as an
    unknown user.
    """
    config_defaults = {
        "metaproxy": "deltaproxy",
    }

    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id,
            overrides={"user": "unknown-user"},
            defaults=config_defaults,
        )
        factory.start(start_timeout=10, max_start_attempts=1)

    assert exc.value.exitcode == salt.defaults.exitcodes.EX_NOUSER, exc.value
    assert "The user is not available." in exc.value.stderr, exc.value


@pytest.mark.slow_test
def test_exit_status_unknown_argument(salt_master, proxy_minion_id):
    """
    Ensure correct exit status when an unknown argument is passed to
    salt-proxy.
    """
    config_defaults = {
        "metaproxy": "deltaproxy",
    }

    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id, defaults=config_defaults
        )
        factory.start("--unknown-argument", start_timeout=10, max_start_attempts=1)

    assert exc.value.exitcode == salt.defaults.exitcodes.EX_USAGE, exc.value
    assert "Usage" in exc.value.stderr, exc.value
    assert "no such option: --unknown-argument" in exc.value.stderr, exc.value


# Hangs on Windows. You can add a timeout to the proxy.run command, but then
# it just times out.
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_exit_status_correct_usage(
    base_env_pillar_tree_root_dir,
    salt_master,
    salt_cli,
    proxy_minion_id,
):
    """
    Ensure the salt-proxy control proxy starts and
    is able to respond to test.ping, additionally ensure that
    the proxies being controlled also respond to test.ping.

    Finally ensure correct exit status when salt-proxy exits correctly.

    Skip on Windows because daemonization not supported
    """

    config_defaults = {
        "metaproxy": "deltaproxy",
    }

    top_file = """
    base:
      '{}':
        - controlproxy
      dummy_proxy_one:
        - dummy_proxy_one
      dummy_proxy_two:
        - dummy_proxy_two
    """.format(
        proxy_minion_id
    )
    controlproxy_pillar_file = """
    proxy:
        proxytype: deltaproxy
        ids:
          - dummy_proxy_one
          - dummy_proxy_two
    """

    dummy_proxy_one_pillar_file = """
    proxy:
      proxytype: dummy
    """

    dummy_proxy_two_pillar_file = """
    proxy:
      proxytype: dummy
    """

    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    controlproxy_tempfile = pytest.helpers.temp_file(
        "controlproxy.sls", controlproxy_pillar_file, base_env_pillar_tree_root_dir
    )
    dummy_proxy_one_tempfile = pytest.helpers.temp_file(
        "dummy_proxy_one.sls",
        dummy_proxy_one_pillar_file,
        base_env_pillar_tree_root_dir,
    )
    dummy_proxy_two_tempfile = pytest.helpers.temp_file(
        "dummy_proxy_two.sls",
        dummy_proxy_two_pillar_file,
        base_env_pillar_tree_root_dir,
    )
    with top_tempfile, controlproxy_tempfile, dummy_proxy_one_tempfile, dummy_proxy_two_tempfile:
        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id,
            defaults=config_defaults,
            extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
            start_timeout=240,
        )

        factory.after_terminate(clear_proxy_minions, salt_master, factory.id)

        factory.start()
        assert factory.is_running()

        # Let's issue a ping the control proxy
        ret = salt_cli.run("test.ping", minion_tgt=proxy_minion_id)
        assert ret.exitcode == 0
        assert ret.json is True

        # Let's issue a ping to one of the controlled proxies
        ret = salt_cli.run("test.ping", minion_tgt="dummy_proxy_one")
        assert ret.exitcode == 0
        assert ret.json is True

        # Let's issue a ping to one of the controlled proxies
        ret = salt_cli.run("test.ping", minion_tgt="dummy_proxy_two")
        assert ret.exitcode == 0
        assert ret.json is True

        # Terminate the proxy minion
        ret = factory.terminate()
        assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret


# Hangs on Windows. You can add a timeout to the proxy.run command, but then
# it just times out.
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_missing_pillar_file(
    salt_factories,
    base_env_pillar_tree_root_dir,
    salt_master,
    salt_cli,
    proxy_minion_id,
):
    """
    Ensure that the control proxy minion starts up when
    pillar files for sub proxies are missing.

    Skip on Windows because daemonization not supported
    """

    config_defaults = {
        "metaproxy": "deltaproxy",
    }

    top_file = """
    base:
      '{}':
        - controlproxy
      dummy_proxy_one:
        - dummy_proxy_one
    """.format(
        proxy_minion_id
    )
    controlproxy_pillar_file = """
    proxy:
        proxytype: deltaproxy
        ids:
          - dummy_proxy_one
          - dummy_proxy_two
    """

    dummy_proxy_one_pillar_file = """
    proxy:
      proxytype: dummy
    """

    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    controlproxy_tempfile = pytest.helpers.temp_file(
        "controlproxy.sls", controlproxy_pillar_file, base_env_pillar_tree_root_dir
    )
    dummy_proxy_one_tempfile = pytest.helpers.temp_file(
        "dummy_proxy_one.sls",
        dummy_proxy_one_pillar_file,
        base_env_pillar_tree_root_dir,
    )
    with top_tempfile, controlproxy_tempfile, dummy_proxy_one_tempfile:
        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id,
            defaults=config_defaults,
            extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
            start_timeout=240,
        )

        factory.after_terminate(clear_proxy_minions, salt_master, factory.id)

        factory.start()
        assert factory.is_running()

        # Let's issue a ping the control proxy
        ret = salt_cli.run("test.ping", minion_tgt=proxy_minion_id)
        assert ret.exitcode == 0
        assert ret.json is True

        # Let's issue a ping to one of the controlled proxies
        ret = salt_cli.run("test.ping", minion_tgt="dummy_proxy_one")
        assert ret.exitcode == 0
        assert ret.json is True

        # Terminate the proxy minion
        ret = factory.terminate()
        assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret


# Hangs on Windows. You can add a timeout to the proxy.run command, but then
# it just times out.
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_invalid_connection(
    salt_factories,
    base_env_pillar_tree_root_dir,
    salt_master,
    salt_cli,
    proxy_minion_id,
):
    """
    Ensure that the control proxy minion starts up when
    pillar files for sub proxies are missing.

    Skip on Windows because daemonization not supported
    """

    config_defaults = {
        "metaproxy": "deltaproxy",
    }

    top_file = """
    base:
      '{}':
        - controlproxy
      dummy_proxy_one:
        - dummy_proxy_one
      broken_proxy_one:
        - broken_proxy_one
      broken_proxy_two:
        - broken_proxy_two
    """.format(
        proxy_minion_id
    )
    controlproxy_pillar_file = """
    proxy:
        proxytype: deltaproxy
        ids:
          - broken_proxy_one
          - broken_proxy_two
          - dummy_proxy_one
    """

    dummy_proxy_one_pillar_file = """
    proxy:
      proxytype: dummy
    """

    broken_proxy_one_pillar_file = """
    proxy:
      proxytype: dummy
      raise_minion_error: True
    """

    broken_proxy_two_pillar_file = """
    proxy:
      proxytype: dummy
      raise_commandexec_error: True
    """

    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    controlproxy_tempfile = salt_master.pillar_tree.base.temp_file(
        "controlproxy.sls", controlproxy_pillar_file
    )
    dummy_proxy_one_tempfile = salt_master.pillar_tree.base.temp_file(
        "dummy_proxy_one.sls", dummy_proxy_one_pillar_file
    )
    broken_proxy_one_tempfile = salt_master.pillar_tree.base.temp_file(
        "broken_proxy_one.sls", broken_proxy_one_pillar_file
    )
    broken_proxy_two_tempfile = salt_master.pillar_tree.base.temp_file(
        "broken_proxy_two.sls", broken_proxy_two_pillar_file
    )
    with top_tempfile, controlproxy_tempfile, dummy_proxy_one_tempfile, broken_proxy_one_tempfile, broken_proxy_two_tempfile:
        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id,
            defaults=config_defaults,
            extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
            start_timeout=240,
        )

        factory.after_terminate(clear_proxy_minions, salt_master, factory.id)

        with factory.started():
            # Let's issue a ping the control proxy
            ret = salt_cli.run("test.ping", minion_tgt=proxy_minion_id)
            assert ret.exitcode == 0
            assert ret.json is True
            # Let's issue a ping to one of the controlled proxies
            ret = salt_cli.run("test.ping", minion_tgt="dummy_proxy_one")
            assert ret.exitcode == 0
            assert ret.json is True

    assert not factory.is_running()
    assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret
