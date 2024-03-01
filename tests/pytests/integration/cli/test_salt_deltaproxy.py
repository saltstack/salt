"""
:codeauthor: Gareth J. Greenaway (ggreenaway@vmware.com)
"""
import logging
import random

import pytest
from pytestshellutils.exceptions import FactoryNotStarted
from saltfactories.utils import random_string

import salt.defaults.exitcodes
from tests.support.helpers import PRE_PYTEST_SKIP_REASON

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_on_spawning_platform(
        reason="Deltaproxy minions do not currently work on spawning platforms.",
    ),
    pytest.mark.core_test,
    pytest.mark.timeout_unless_on_windows(400),
]


@pytest.fixture(scope="package", autouse=True)
def _skip_on_tcp_transport(request):
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

    assert exc.value.process_result.returncode == salt.defaults.exitcodes.EX_USAGE
    assert "Usage" in exc.value.process_result.stderr, exc.value
    assert "error: salt-proxy requires --proxyid" in exc.value.process_result.stderr


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

    assert exc.value.process_result.returncode == salt.defaults.exitcodes.EX_NOUSER
    assert "The user is not available." in exc.value.process_result.stderr


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

    assert exc.value.process_result.returncode == salt.defaults.exitcodes.EX_USAGE
    assert "Usage" in exc.value.process_result.stderr
    assert "no such option: --unknown-argument" in exc.value.process_result.stderr


# Hangs on Windows. You can add a timeout to the proxy.run command, but then
# it just times out.
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
@pytest.mark.parametrize(
    "parallel_startup",
    [True, False],
    ids=["parallel_startup=True", "parallel_startup=False"],
)
def test_exit_status_correct_usage(
    salt_master,
    salt_cli,
    proxy_minion_id,
    parallel_startup,
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
    proxy_one = "dummy_proxy_one"
    proxy_two = "dummy_proxy_two"

    top_file = """
    base:
      {control}:
        - controlproxy
      {one}:
        - {one}
      {two}:
        - {two}
    """.format(
        control=proxy_minion_id,
        one=proxy_one,
        two=proxy_two,
    )
    controlproxy_pillar_file = """
    proxy:
        proxytype: deltaproxy
        parallel_startup: {}
        ids:
          - {}
          - {}
    """.format(
        parallel_startup, proxy_one, proxy_two
    )

    dummy_proxy_one_pillar_file = """
    proxy:
      proxytype: dummy
    """

    dummy_proxy_two_pillar_file = """
    proxy:
      proxytype: dummy
    """

    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    controlproxy_tempfile = salt_master.pillar_tree.base.temp_file(
        "controlproxy.sls", controlproxy_pillar_file
    )
    dummy_proxy_one_tempfile = salt_master.pillar_tree.base.temp_file(
        f"{proxy_one}.sls",
        dummy_proxy_one_pillar_file,
    )
    dummy_proxy_two_tempfile = salt_master.pillar_tree.base.temp_file(
        f"{proxy_two}.sls",
        dummy_proxy_two_pillar_file,
    )
    with top_tempfile, controlproxy_tempfile, dummy_proxy_one_tempfile, dummy_proxy_two_tempfile:
        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id,
            defaults=config_defaults,
            extra_cli_arguments_after_first_start_failure=["--log-level=info"],
            start_timeout=320,
        )

        for minion_id in (proxy_minion_id, proxy_one, proxy_two):
            factory.before_start(
                pytest.helpers.remove_stale_proxy_minion_cache_file, factory, minion_id
            )
            factory.after_terminate(
                pytest.helpers.remove_stale_minion_key, salt_master, minion_id
            )
            factory.after_terminate(
                pytest.helpers.remove_stale_proxy_minion_cache_file, factory, minion_id
            )

        with factory.started():
            assert factory.is_running()

            # Let's issue a ping the control proxy
            ret = salt_cli.run("test.ping", minion_tgt=proxy_minion_id)
            assert ret.returncode == 0
            assert ret.data is True

            # Let's issue a ping to one of the controlled proxies
            ret = salt_cli.run("test.ping", minion_tgt=proxy_one)
            assert ret.returncode == 0
            assert ret.data is True

            # Let's issue a ping to one of the controlled proxies
            ret = salt_cli.run("test.ping", minion_tgt=proxy_two)
            assert ret.returncode == 0
            assert ret.data is True

        # Terminate the proxy minion
        ret = factory.terminate()
        assert ret.returncode == salt.defaults.exitcodes.EX_OK, ret


# Hangs on Windows. You can add a timeout to the proxy.run command, but then
# it just times out.
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
@pytest.mark.parametrize(
    "parallel_startup",
    [True, False],
    ids=["parallel_startup=True", "parallel_startup=False"],
)
def test_missing_pillar_file(
    salt_master,
    salt_cli,
    proxy_minion_id,
    parallel_startup,
):
    """
    Ensure that the control proxy minion starts up when
    pillar files for sub proxies are missing.

    Skip on Windows because daemonization not supported
    """

    config_defaults = {
        "metaproxy": "deltaproxy",
    }
    proxy_one = "dummy_proxy_one"
    proxy_two = "dummy_proxy_two"

    top_file = """
    base:
      {control}:
        - controlproxy
      {one}:
        - {one}
    """.format(
        control=proxy_minion_id,
        one=proxy_one,
    )
    controlproxy_pillar_file = """
    proxy:
        proxytype: deltaproxy
        parallel_startup: {}
        ids:
          - {}
          - {}
    """.format(
        parallel_startup, proxy_one, proxy_two
    )

    dummy_proxy_one_pillar_file = """
    proxy:
      proxytype: dummy
    """

    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    controlproxy_tempfile = salt_master.pillar_tree.base.temp_file(
        "controlproxy.sls", controlproxy_pillar_file
    )
    dummy_proxy_one_tempfile = salt_master.pillar_tree.base.temp_file(
        f"{proxy_one}.sls",
        dummy_proxy_one_pillar_file,
    )
    with top_tempfile, controlproxy_tempfile, dummy_proxy_one_tempfile:
        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id,
            defaults=config_defaults,
            extra_cli_arguments_after_first_start_failure=["--log-level=info"],
            start_timeout=320,
        )

        for minion_id in (proxy_minion_id, proxy_one, proxy_two):
            factory.before_start(
                pytest.helpers.remove_stale_proxy_minion_cache_file, factory, minion_id
            )
            factory.after_terminate(
                pytest.helpers.remove_stale_minion_key, salt_master, minion_id
            )
            factory.after_terminate(
                pytest.helpers.remove_stale_proxy_minion_cache_file, factory, minion_id
            )

        with factory.started():
            assert factory.is_running()

            # Let's issue a ping the control proxy
            ret = salt_cli.run("test.ping", minion_tgt=proxy_minion_id)
            assert ret.returncode == 0
            assert ret.data is True

            # Let's issue a ping to one of the controlled proxies
            ret = salt_cli.run("test.ping", minion_tgt="dummy_proxy_one")
            assert ret.returncode == 0
            assert ret.data is True

        # Terminate the proxy minion
        ret = factory.terminate()
        assert ret.returncode == salt.defaults.exitcodes.EX_OK, ret


# Hangs on Windows. You can add a timeout to the proxy.run command, but then
# it just times out.
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
@pytest.mark.parametrize(
    "parallel_startup",
    [True, False],
    ids=["parallel_startup=True", "parallel_startup=False"],
)
def test_invalid_connection(
    salt_master,
    salt_cli,
    proxy_minion_id,
    parallel_startup,
):
    """
    Ensure that the control proxy minion starts up when
    pillar files for sub proxies are missing.

    Skip on Windows because daemonization not supported
    """

    config_defaults = {
        "metaproxy": "deltaproxy",
    }
    proxy_one = "dummy_proxy_one"
    broken_proxy_one = "broken_proxy_one"
    broken_proxy_two = "broken_proxy_two"

    top_file = """
    base:
      {control}:
        - controlproxy
      {one}:
        - {one}
      {broken_proxy_one}:
        - {broken_proxy_one}
      {broken_proxy_two}:
        - {broken_proxy_two}
    """.format(
        control=proxy_minion_id,
        one=proxy_one,
        broken_proxy_one=broken_proxy_one,
        broken_proxy_two=broken_proxy_two,
    )
    controlproxy_pillar_file = """
    proxy:
        proxytype: deltaproxy
        parallel_startup: {}
        ids:
          - {}
          - {}
          - {}
    """.format(
        parallel_startup, broken_proxy_one, broken_proxy_two, proxy_one
    )

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
        f"{proxy_one}.sls",
        dummy_proxy_one_pillar_file,
    )
    broken_proxy_one_tempfile = salt_master.pillar_tree.base.temp_file(
        f"{broken_proxy_one}.sls", broken_proxy_one_pillar_file
    )
    broken_proxy_two_tempfile = salt_master.pillar_tree.base.temp_file(
        f"{broken_proxy_two}.sls", broken_proxy_two_pillar_file
    )
    with top_tempfile, controlproxy_tempfile, dummy_proxy_one_tempfile, broken_proxy_one_tempfile, broken_proxy_two_tempfile:
        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id,
            defaults=config_defaults,
            extra_cli_arguments_after_first_start_failure=["--log-level=info"],
            start_timeout=320,
        )

        for minion_id in (
            proxy_minion_id,
            proxy_one,
            broken_proxy_one,
            broken_proxy_two,
        ):
            factory.before_start(
                pytest.helpers.remove_stale_proxy_minion_cache_file, factory, minion_id
            )
            factory.after_terminate(
                pytest.helpers.remove_stale_minion_key, salt_master, minion_id
            )
            factory.after_terminate(
                pytest.helpers.remove_stale_proxy_minion_cache_file, factory, minion_id
            )

        with factory.started():
            # Let's issue a ping the control proxy
            ret = salt_cli.run("test.ping", minion_tgt=proxy_minion_id)
            assert ret.returncode == 0
            assert ret.data is True
            # Let's issue a ping to one of the controlled proxies
            ret = salt_cli.run("test.ping", minion_tgt=proxy_one)
            assert ret.returncode == 0
            assert ret.data is True

    assert not factory.is_running()
    assert ret.returncode == salt.defaults.exitcodes.EX_OK, ret


@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
@pytest.mark.parametrize(
    "parallel_startup",
    [True, False],
    ids=["parallel_startup=True", "parallel_startup=False"],
)
def test_custom_proxy_module(
    salt_master,
    salt_cli,
    proxy_minion_id,
    parallel_startup,
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
    proxy_one = "custom_dummy_proxy_one"
    proxy_two = "custom_dummy_proxy_two"

    top_file = """
    base:
      {control}:
        - controlproxy
      {one}:
        - {one}
      {two}:
        - {two}
    """.format(
        control=proxy_minion_id,
        one=proxy_one,
        two=proxy_two,
    )
    controlproxy_pillar_file = """
    proxy:
        proxytype: deltaproxy
        parallel_startup: {}
        ids:
          - {}
          - {}
    """.format(
        parallel_startup, proxy_one, proxy_two
    )

    dummy_proxy_one_pillar_file = """
    proxy:
      proxytype: custom_dummy
    """

    dummy_proxy_two_pillar_file = """
    proxy:
      proxytype: custom_dummy
    """

    module_contents = """
__proxyenabled__ = ["custom_dummy"]

def __virtual__():
    return True

def init(opts):
    return True

def ping():
    return True
    """

    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    controlproxy_tempfile = salt_master.pillar_tree.base.temp_file(
        "controlproxy.sls", controlproxy_pillar_file
    )
    dummy_proxy_one_tempfile = salt_master.pillar_tree.base.temp_file(
        f"{proxy_one}.sls",
        dummy_proxy_one_pillar_file,
    )
    dummy_proxy_two_tempfile = salt_master.pillar_tree.base.temp_file(
        f"{proxy_two}.sls",
        dummy_proxy_two_pillar_file,
    )

    custom_proxy_module = salt_master.state_tree.base.temp_file(
        "_proxy/custom_dummy.py", module_contents
    )
    with top_tempfile, controlproxy_tempfile, dummy_proxy_one_tempfile, dummy_proxy_two_tempfile, custom_proxy_module:
        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id,
            defaults=config_defaults,
            extra_cli_arguments_after_first_start_failure=["--log-level=info"],
            start_timeout=320,
        )

        for minion_id in (proxy_minion_id, proxy_one, proxy_two):
            factory.before_start(
                pytest.helpers.remove_stale_proxy_minion_cache_file, factory, minion_id
            )
            factory.after_terminate(
                pytest.helpers.remove_stale_minion_key, salt_master, minion_id
            )
            factory.after_terminate(
                pytest.helpers.remove_stale_proxy_minion_cache_file, factory, minion_id
            )

        with factory.started():
            assert factory.is_running()

            # Let's issue a ping the control proxy
            ret = salt_cli.run("test.ping", minion_tgt=proxy_minion_id)
            assert ret.returncode == 0
            assert ret.data is True

            # Let's issue a ping to one of the controlled proxies
            ret = salt_cli.run("test.ping", minion_tgt=proxy_one)
            assert ret.returncode == 0
            assert ret.data is True

            # Let's issue a ping to one of the controlled proxies
            ret = salt_cli.run("test.ping", minion_tgt=proxy_two)
            assert ret.returncode == 0
            assert ret.data is True

        # Terminate the proxy minion
        ret = factory.terminate()
        assert ret.returncode == salt.defaults.exitcodes.EX_OK, ret


@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
@pytest.mark.parametrize(
    "parallel_startup",
    [True, False],
    ids=["parallel_startup=True", "parallel_startup=False"],
)
def test_custom_proxy_module_raise_exception(
    salt_master,
    salt_cli,
    proxy_minion_id,
    parallel_startup,
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
    proxy_one = "custom_dummy_proxy_one"
    proxy_two = "custom_dummy_proxy_two"

    top_file = """
    base:
      {control}:
        - controlproxy
      {one}:
        - {one}
      {two}:
        - {two}
    """.format(
        control=proxy_minion_id,
        one=proxy_one,
        two=proxy_two,
    )
    controlproxy_pillar_file = """
    proxy:
        proxytype: deltaproxy
        parallel_startup: {}
        ids:
          - {}
          - {}
    """.format(
        parallel_startup, proxy_one, proxy_two
    )

    dummy_proxy_one_pillar_file = """
    proxy:
      proxytype: custom_dummy
    """

    dummy_proxy_two_pillar_file = """
    proxy:
      proxytype: dummy
    """

    module_contents = """
__proxyenabled__ = ["custom_dummy"]

def __virtual__():
    return True

def init(opts):
    raise Exception("Something has gone horribly wrong.")

def ping():
    return True
    """

    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    controlproxy_tempfile = salt_master.pillar_tree.base.temp_file(
        "controlproxy.sls", controlproxy_pillar_file
    )
    dummy_proxy_one_tempfile = salt_master.pillar_tree.base.temp_file(
        f"{proxy_one}.sls",
        dummy_proxy_one_pillar_file,
    )
    dummy_proxy_two_tempfile = salt_master.pillar_tree.base.temp_file(
        f"{proxy_two}.sls",
        dummy_proxy_two_pillar_file,
    )

    custom_proxy_module = salt_master.state_tree.base.temp_file(
        "_proxy/custom_dummy.py", module_contents
    )
    with top_tempfile, controlproxy_tempfile, dummy_proxy_one_tempfile, dummy_proxy_two_tempfile, custom_proxy_module:
        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id,
            defaults=config_defaults,
            extra_cli_arguments_after_first_start_failure=["--log-level=info"],
            start_timeout=320,
        )

        for minion_id in (proxy_minion_id, proxy_one, proxy_two):
            factory.before_start(
                pytest.helpers.remove_stale_proxy_minion_cache_file, factory, minion_id
            )
            factory.after_terminate(
                pytest.helpers.remove_stale_minion_key, salt_master, minion_id
            )
            factory.after_terminate(
                pytest.helpers.remove_stale_proxy_minion_cache_file, factory, minion_id
            )

        with factory.started():
            assert factory.is_running()

            # Let's issue a ping the control proxy
            ret = salt_cli.run("test.ping", minion_tgt=proxy_minion_id)
            assert ret.returncode == 0
            assert ret.data is True

            # Let's issue a ping to one of the controlled proxies
            ret = salt_cli.run("test.ping", minion_tgt=proxy_one)
            assert ret.returncode == 1
            assert "Minion did not return" in ret.data

            # Let's issue a ping to one of the controlled proxies
            ret = salt_cli.run("test.ping", minion_tgt=proxy_two)
            assert ret.returncode == 0
            assert ret.data is True

        # Terminate the proxy minion
        ret = factory.terminate()
        assert ret.returncode == salt.defaults.exitcodes.EX_OK, ret


# Hangs on Windows. You can add a timeout to the proxy.run command, but then
# it just times out.
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
@pytest.mark.parametrize(
    "parallel_startup",
    [True, False],
    ids=["parallel_startup=True", "parallel_startup=False"],
)
def test_exit_status_correct_usage_large_number_of_minions(
    salt_master,
    salt_cli,
    proxy_minion_id,
    parallel_startup,
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
    sub_proxies = [
        "proxy_one",
        "proxy_two",
        "proxy_three",
        "proxy_four",
        "proxy_five",
        "proxy_six",
        "proxy_seven",
        "proxy_eight",
        "proxy_nine",
        "proxy_ten",
        "proxy_eleven",
        "proxy_twelve",
        "proxy_thirteen",
        "proxy_fourteen",
        "proxy_fifteen",
        "proxy_sixteen",
        "proxy_seventeen",
        "proxy_eighteen",
        "proxy_nineteen",
        "proxy_twenty",
        "proxy_twenty_one",
        "proxy_twenty_two",
        "proxy_twenty_three",
        "proxy_twenty_four",
        "proxy_twenty_five",
        "proxy_twenty_six",
        "proxy_twenty_seven",
        "proxy_twenty_eight",
        "proxy_twenty_nine",
        "proxy_thirty",
        "proxy_thirty_one",
        "proxy_thirty_two",
    ]

    top_file = """
    base:
      {control}:
        - controlproxy
    """.format(
        control=proxy_minion_id,
    )
    controlproxy_pillar_file = f"""
    proxy:
        proxytype: deltaproxy
        parallel_startup: {parallel_startup}
        ids:
    """

    dummy_proxy_pillar_file = """
    proxy:
      proxytype: dummy
    """

    for minion_id in sub_proxies:
        top_file += f"""
      {minion_id}:
        - dummy"""

        controlproxy_pillar_file += f"""
            - {minion_id}
        """

    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    controlproxy_tempfile = salt_master.pillar_tree.base.temp_file(
        "controlproxy.sls", controlproxy_pillar_file
    )
    dummy_proxy_tempfile = salt_master.pillar_tree.base.temp_file(
        "dummy.sls",
        dummy_proxy_pillar_file,
    )
    with top_tempfile, controlproxy_tempfile, dummy_proxy_tempfile:

        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id,
            defaults=config_defaults,
            extra_cli_arguments_after_first_start_failure=["--log-level=info"],
            start_timeout=320,
        )

        for minion_id in [proxy_minion_id] + sub_proxies:
            factory.before_start(
                pytest.helpers.remove_stale_proxy_minion_cache_file,
                factory,
                minion_id,
            )
            factory.after_terminate(
                pytest.helpers.remove_stale_minion_key, salt_master, minion_id
            )
            factory.after_terminate(
                pytest.helpers.remove_stale_proxy_minion_cache_file,
                factory,
                minion_id,
            )

        with factory.started():
            assert factory.is_running()

            # Let's issue a ping the control proxy
            ret = salt_cli.run("test.ping", minion_tgt=proxy_minion_id)
            assert ret.returncode == 0
            assert ret.data is True

            for minion_id in random.sample(sub_proxies, 4):
                # Let's issue a ping to one of the controlled proxies
                ret = salt_cli.run("test.ping", minion_tgt=minion_id)
                assert ret.returncode == 0
                assert ret.data is True

    # Terminate the proxy minion
    ret = factory.terminate()
    assert ret.returncode == salt.defaults.exitcodes.EX_OK, ret
