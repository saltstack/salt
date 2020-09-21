"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.shell.syndic
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import logging
import os
import time

import pytest
import salt.defaults.exitcodes
from saltfactories.exceptions import FactoryNotStarted
from saltfactories.utils import random_string
from tests.support.helpers import PRE_PYTEST_SKIP, PRE_PYTEST_SKIP_REASON, slowTest

log = logging.getLogger(__name__)

pytestmark = pytest.mark.windows_whitelisted


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


@slowTest
@PRE_PYTEST_SKIP
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_exit_status_unknown_user(salt_master, syndic_id):
    """
    Ensure correct exit status when the syndic is configured to run as an unknown user.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.get_salt_syndic_daemon(
            syndic_id, config_overrides={"user": "unknown-user"}
        )
        factory.before_start_callbacks.clear()
        factory.start(start_timeout=10, max_start_attempts=1)

    assert exc.value.exitcode == salt.defaults.exitcodes.EX_NOUSER, exc.value
    assert "The user is not available." in exc.value.stderr, exc.value


@slowTest
@PRE_PYTEST_SKIP
def test_exit_status_unknown_argument(salt_master, syndic_id):
    """
    Ensure correct exit status when an unknown argument is passed to salt-syndic.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.get_salt_syndic_daemon(syndic_id)
        factory.before_start_callbacks.clear()
        factory.start("--unknown-argument", start_timeout=10, max_start_attempts=1)

    assert exc.value.exitcode == salt.defaults.exitcodes.EX_USAGE, exc.value
    assert "Usage" in exc.value.stderr, exc.value
    assert "no such option: --unknown-argument" in exc.value.stderr, exc.value


@slowTest
@PRE_PYTEST_SKIP
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_exit_status_correct_usage(salt_master, syndic_id):
    factory = salt_master.get_salt_syndic_daemon(
        syndic_id,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
        config_defaults={"transport": salt_master.config["transport"]},
    )
    factory.start()
    assert factory.is_running()
    time.sleep(0.5)
    ret = factory.terminate()
    assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret
