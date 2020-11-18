"""
    :codeauthor: Thayne Harbaugh (tharbaug@adobe.com)

    tests.pytests.integration.cli.test_proxy
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Various integration tests for the salt-proxy executable.
"""

import logging
import time

import pytest
import salt.defaults.exitcodes
from saltfactories.exceptions import FactoryNotStarted
from saltfactories.utils import random_string
from tests.support.helpers import PRE_PYTEST_SKIP_REASON, slowTest

log = logging.getLogger(__name__)


@pytest.fixture
def proxy_minion_id(salt_factories, salt_master):
    _proxy_minion_id = random_string("proxy-minion-")

    try:
        yield _proxy_minion_id
    finally:
        # Remove stale key if it exists
        pytest.helpers.remove_stale_minion_key(salt_master, _proxy_minion_id)


@slowTest
def test_exit_status_no_proxyid(salt_master, proxy_minion_id):
    """
    Ensure correct exit status when --proxyid argument is missing.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.get_salt_proxy_minion_daemon(
            proxy_minion_id, include_proxyid_cli_flag=False
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
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.get_salt_proxy_minion_daemon(
            proxy_minion_id, config_overrides={"user": "unknown-user"}
        )
        factory.start(start_timeout=10, max_start_attempts=1)

    assert exc.value.exitcode == salt.defaults.exitcodes.EX_NOUSER, exc.value
    assert "The user is not available." in exc.value.stderr, exc.value


@slowTest
def test_exit_status_unknown_argument(salt_master, proxy_minion_id):
    """
    Ensure correct exit status when an unknown argument is passed to
    salt-proxy.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.get_salt_proxy_minion_daemon(proxy_minion_id)
        factory.start("--unknown-argument", start_timeout=10, max_start_attempts=1)

    assert exc.value.exitcode == salt.defaults.exitcodes.EX_USAGE, exc.value
    assert "Usage" in exc.value.stderr, exc.value
    assert "no such option: --unknown-argument" in exc.value.stderr, exc.value


# Hangs on Windows. You can add a timeout to the proxy.run command, but then
# it just times out.
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_exit_status_correct_usage(salt_master, proxy_minion_id):
    """
    Ensure correct exit status when salt-proxy starts correctly.

    Skip on Windows because daemonization not supported
    """
    factory = salt_master.get_salt_proxy_minion_daemon(
        proxy_minion_id,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
        config_defaults={"transport": salt_master.config["transport"]},
    )
    factory.start()
    assert factory.is_running()
    time.sleep(0.5)
    ret = factory.terminate()
    assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret
