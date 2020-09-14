"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.shell.minion
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""


import logging
import os
import time

import pytest
import salt.defaults.exitcodes
from saltfactories.exceptions import FactoryNotStarted
from saltfactories.utils import random_string
from tests.support.helpers import PRE_PYTEST_SKIP_REASON, slowTest

log = logging.getLogger(__name__)

pytestmark = pytest.mark.windows_whitelisted


@pytest.fixture
def minion_id(salt_factories, salt_master):
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


@slowTest
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_exit_status_unknown_user(salt_master, minion_id):
    """
    Ensure correct exit status when the minion is configured to run as an unknown user.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.get_salt_minion_daemon(
            minion_id, config_overrides={"user": "unknown-user"}
        )
        factory.start(start_timeout=10, max_start_attempts=1)

    assert exc.value.exitcode == salt.defaults.exitcodes.EX_NOUSER, exc.value
    assert "The user is not available." in exc.value.stderr, exc.value


@slowTest
def test_exit_status_unknown_argument(salt_master, minion_id):
    """
    Ensure correct exit status when an unknown argument is passed to salt-minion.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_master.get_salt_minion_daemon(minion_id)
        factory.start("--unknown-argument", start_timeout=10, max_start_attempts=1)

    assert exc.value.exitcode == salt.defaults.exitcodes.EX_USAGE, exc.value
    assert "Usage" in exc.value.stderr, exc.value
    assert "no such option: --unknown-argument" in exc.value.stderr, exc.value


@slowTest
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_exit_status_correct_usage(salt_master, minion_id):
    factory = salt_master.get_salt_minion_daemon(
        minion_id,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
        config_defaults={"transport": salt_master.config["transport"]},
    )
    factory.start()
    assert factory.is_running()
    time.sleep(0.5)
    ret = factory.terminate()
    assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret
