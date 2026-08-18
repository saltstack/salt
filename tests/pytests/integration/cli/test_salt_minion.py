import logging
import os

import pytest
from pytestshellutils.exceptions import FactoryNotStarted
from saltfactories.utils import random_string

import salt.defaults.exitcodes
from tests.conftest import FIPS_TESTRUN
from tests.support.helpers import PRE_PYTEST_SKIP_REASON

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
]

log = logging.getLogger(__name__)


@pytest.fixture
def minion_id(salt_master):
    _minion_id = random_string("minion-")

    try:
        yield _minion_id
    finally:
        # Remove stale key if it exists
        minion_key_file = os.path.join(
            salt_master.config["pki_dir"], "minions", _minion_id
        )
        if os.path.exists(minion_key_file):
            log.debug("Minion %r KEY FILE: %s", _minion_id, minion_key_file)
            os.unlink(minion_key_file)


@pytest.mark.skip_on_windows(reason="Windows does not do user checks")
def test_exit_status_unknown_user(salt_master, minion_id):
    """
    Ensure correct exit status when the minion is configured to run as an unknown user.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.salt_minion_daemon(
            minion_id,
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


def test_exit_status_unknown_argument(salt_master, minion_id):
    """
    Ensure correct exit status when an unknown argument is passed to salt-minion.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.salt_minion_daemon(
            minion_id,
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


@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_exit_status_correct_usage(salt_master, minion_id, salt_cli):
    factory = salt_master.salt_minion_daemon(
        minion_id,
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
    ret = salt_cli.run("test.ping", minion_tgt=minion_id)
    assert ret.returncode == 0
    assert ret.data is True
    # Terminate
    ret = factory.terminate()
    assert ret.returncode == salt.defaults.exitcodes.EX_OK, ret
