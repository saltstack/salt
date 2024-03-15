"""
:codeauthor: Gareth J. Greenaway (ggreenaway@vmware.com)
"""

import logging
import random

import pytest
from saltfactories.utils import random_string

import salt.defaults.exitcodes
from tests.support.helpers import PRE_PYTEST_SKIP_REASON

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_on_spawning_platform(
        reason="Deltaproxy minions do not currently work on spawning platforms.",
    ),
    pytest.mark.core_test,
    pytest.mark.timeout_unless_on_windows(320),
]


@pytest.fixture(scope="package")
def salt_master(salt_factories):
    config_defaults = {
        "open_mode": True,
    }
    salt_master = salt_factories.salt_master_daemon(
        "deltaproxy-functional-master", defaults=config_defaults
    )
    with salt_master.started():
        yield salt_master


@pytest.fixture(scope="package")
def salt_cli(salt_master):
    """
    The ``salt`` CLI as a fixture against the running master
    """
    assert salt_master.is_running()
    return salt_master.salt_cli(timeout=30)


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
    controlproxy_pillar_file = """
    proxy:
        proxytype: deltaproxy
        parallel_startup: {}
        ids:
    """.format(
        parallel_startup
    )

    dummy_proxy_pillar_file = """
    proxy:
      proxytype: dummy
    """

    for minion_id in sub_proxies:
        top_file += """
      {minion_id}:
        - dummy""".format(
            minion_id=minion_id,
        )

        controlproxy_pillar_file += """
            - {}
        """.format(
            minion_id,
        )

    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    controlproxy_tempfile = salt_master.pillar_tree.base.temp_file(
        "controlproxy.sls", controlproxy_pillar_file
    )
    dummy_proxy_tempfile = salt_master.pillar_tree.base.temp_file(
        "dummy.sls",
        dummy_proxy_pillar_file,
    )
    with top_tempfile, controlproxy_tempfile, dummy_proxy_tempfile:
        with salt_master.started():
            assert salt_master.is_running()

            factory = salt_master.salt_proxy_minion_daemon(
                proxy_minion_id,
                defaults=config_defaults,
                extra_cli_arguments_after_first_start_failure=["--log-level=info"],
                start_timeout=240,
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

        # Terminate the salt master
        ret = salt_master.terminate()
        assert ret.returncode == salt.defaults.exitcodes.EX_OK, ret
