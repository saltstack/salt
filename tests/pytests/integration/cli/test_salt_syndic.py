import logging
import os
import time

import pytest
from pytestshellutils.exceptions import FactoryNotStarted
from saltfactories.utils import random_string

import salt.defaults.exitcodes
from tests.support.helpers import PRE_PYTEST_SKIP, PRE_PYTEST_SKIP_REASON

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]

log = logging.getLogger(__name__)


@pytest.fixture
def syndic_id(salt_factories, salt_master):
    _syndic_id = random_string("syndic-")

    try:
        yield _syndic_id
    finally:
        # Remove stale key if it exists
        syndic_key_file = os.path.join(
            salt_master.config["pki_dir"], "syndics", _syndic_id
        )
        if os.path.exists(syndic_key_file):
            log.debug("syndic %r KEY FILE: %s", _syndic_id, syndic_key_file)
            os.unlink(syndic_key_file)


@PRE_PYTEST_SKIP
@pytest.mark.skip_on_windows(reason="Windows does not do user checks")
def test_exit_status_unknown_user(salt_master, syndic_id):
    """
    Ensure correct exit status when the syndic is configured to run as an unknown user.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.salt_syndic_daemon(
            syndic_id, overrides={"user": "unknown-user"}
        )
        factory.before_start_callbacks.clear()
        factory.start(start_timeout=10, max_start_attempts=1)

    assert exc.value.process_result.returncode == salt.defaults.exitcodes.EX_NOUSER
    assert "The user is not available." in exc.value.process_result.stderr


@PRE_PYTEST_SKIP
def test_exit_status_unknown_argument(salt_master, syndic_id):
    """
    Ensure correct exit status when an unknown argument is passed to salt-syndic.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.salt_syndic_daemon(syndic_id)
        factory.before_start_callbacks.clear()
        factory.start("--unknown-argument", start_timeout=10, max_start_attempts=1)

    assert exc.value.process_result.returncode == salt.defaults.exitcodes.EX_USAGE
    assert "Usage" in exc.value.process_result.stderr
    assert "no such option: --unknown-argument" in exc.value.process_result.stderr


@PRE_PYTEST_SKIP
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_exit_status_correct_usage(salt_master, syndic_id):
    factory = salt_master.salt_syndic_daemon(
        syndic_id,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
        defaults={"transport": salt_master.config["transport"]},
    )
    factory.start()
    assert factory.is_running()
    time.sleep(0.5)
    ret = factory.terminate()
    assert ret.returncode == salt.defaults.exitcodes.EX_OK, ret
