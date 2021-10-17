import logging
import os

import pytest
import salt.defaults.exitcodes
from saltfactories.exceptions import FactoryNotStarted
from saltfactories.utils import random_string
from tests.support.helpers import PRE_PYTEST_SKIP_REASON

pytestmark = [
    pytest.mark.slow_test,
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
            minion_id, overrides={"user": "unknown-user"}
        )
        factory.start(start_timeout=10, max_start_attempts=1)

    assert exc.value.exitcode == salt.defaults.exitcodes.EX_NOUSER, exc.value
    assert "The user is not available." in exc.value.stderr, exc.value


def test_exit_status_unknown_argument(salt_master, minion_id):
    """
    Ensure correct exit status when an unknown argument is passed to salt-minion.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.salt_minion_daemon(minion_id)
        factory.start("--unknown-argument", start_timeout=10, max_start_attempts=1)

    assert exc.value.exitcode == salt.defaults.exitcodes.EX_USAGE, exc.value
    assert "Usage" in exc.value.stderr, exc.value
    assert "no such option: --unknown-argument" in exc.value.stderr, exc.value


@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_exit_status_correct_usage(salt_master, minion_id, salt_cli):
    factory = salt_master.salt_minion_daemon(
        minion_id,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
        defaults={"transport": salt_master.config["transport"]},
    )
    factory.start()
    assert factory.is_running()
    # Let's issue a ping before terminating
    ret = salt_cli.run("test.ping", minion_tgt=minion_id)
    assert ret.exitcode == 0
    assert ret.json is True
    # Terminate
    ret = factory.terminate()
    assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret
