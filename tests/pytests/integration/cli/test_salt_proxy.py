"""
:codeauthor: Thayne Harbaugh (tharbaug@adobe.com)
"""

import logging

import pytest
from pytestshellutils.exceptions import FactoryNotStarted
from saltfactories.utils import random_string

import salt.defaults.exitcodes
from tests.conftest import FIPS_TESTRUN
from tests.support.helpers import PRE_PYTEST_SKIP_REASON

log = logging.getLogger(__name__)


@pytest.fixture
def proxy_minion_id(salt_master):
    _proxy_minion_id = random_string("proxy-minion-")

    try:
        yield _proxy_minion_id
    finally:
        # Remove stale key if it exists
        pytest.helpers.remove_stale_minion_key(salt_master, _proxy_minion_id)


@pytest.mark.core_test
def test_exit_status_no_proxyid(salt_master, proxy_minion_id):
    """
    Ensure correct exit status when --proxyid argument is missing.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id,
            include_proxyid_cli_flag=False,
            overrides={
                "fips_mode": FIPS_TESTRUN,
                "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
                "signing_algorithm": (
                    "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
                ),
            },
        )
        factory.start(start_timeout=10, max_start_attempts=1)

    assert exc.value.process_result.returncode == salt.defaults.exitcodes.EX_USAGE
    assert "Usage" in exc.value.process_result.stderr
    assert "error: salt-proxy requires --proxyid" in exc.value.process_result.stderr


@pytest.mark.skip_on_windows(reason="Windows does not do user checks")
@pytest.mark.core_test
def test_exit_status_unknown_user(salt_master, proxy_minion_id):
    """
    Ensure correct exit status when the proxy is configured to run as an
    unknown user.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id,
            overrides={
                "user": "unknown-user",
                "fips_mode": FIPS_TESTRUN,
                "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
                "signing_algorithm": (
                    "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
                ),
            },
        )
        factory.start(start_timeout=10, max_start_attempts=1)

    assert exc.value.process_result.returncode == salt.defaults.exitcodes.EX_NOUSER
    assert "The user is not available." in exc.value.process_result.stderr


@pytest.mark.core_test
def test_exit_status_unknown_argument(salt_master, proxy_minion_id):
    """
    Ensure correct exit status when an unknown argument is passed to
    salt-proxy.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.salt_proxy_minion_daemon(
            proxy_minion_id,
            overrides={
                "fips_mode": FIPS_TESTRUN,
                "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
                "signing_algorithm": (
                    "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
                ),
            },
        )
        factory.start("--unknown-argument", start_timeout=10, max_start_attempts=1)

    assert exc.value.process_result.returncode == salt.defaults.exitcodes.EX_USAGE
    assert "Usage" in exc.value.process_result.stderr
    assert "no such option: --unknown-argument" in exc.value.process_result.stderr


# Hangs on Windows. You can add a timeout to the proxy.run command, but then
# it just times out.
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_exit_status_correct_usage(salt_master, proxy_minion_id, salt_cli):
    """
    Ensure correct exit status when salt-proxy starts correctly.

    Skip on Windows because daemonization not supported
    """
    factory = salt_master.salt_proxy_minion_daemon(
        proxy_minion_id,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
        defaults={"transport": salt_master.config["transport"]},
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        },
    )
    factory.start()
    assert factory.is_running()
    # Let's issue a ping before terminating
    ret = salt_cli.run("test.ping", minion_tgt=proxy_minion_id)
    assert ret.returncode == 0
    assert ret.data is True
    # Terminate the proxy minion
    ret = factory.terminate()
    assert ret.returncode == salt.defaults.exitcodes.EX_OK, ret
