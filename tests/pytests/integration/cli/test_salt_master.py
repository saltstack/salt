"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.shell.master
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""


import logging
import time

import pytest
import salt.defaults.exitcodes
from saltfactories.exceptions import FactoryNotStarted
from saltfactories.utils import random_string
from tests.support.helpers import PRE_PYTEST_SKIP_REASON, slowTest

log = logging.getLogger(__name__)

pytestmark = pytest.mark.windows_whitelisted


@pytest.fixture
def master_id():
    return random_string("master-")


@slowTest
def test_exit_status_unknown_user(salt_factories, master_id):
    """
    Ensure correct exit status when the master is configured to run as an unknown user.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_factories.get_salt_master_daemon(
            master_id, config_overrides={"user": "unknown-user"}
        )
        factory.start(start_timeout=10, max_start_attempts=1)

    assert exc.value.exitcode == salt.defaults.exitcodes.EX_NOUSER, exc.value
    assert "The user is not available." in exc.value.stderr, exc.value


@slowTest
def test_exit_status_unknown_argument(salt_factories, master_id):
    """
    Ensure correct exit status when an unknown argument is passed to salt-master.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_factories.get_salt_master_daemon(master_id)
        factory.start("--unknown-argument", start_timeout=10, max_start_attempts=1)
    assert exc.value.exitcode == salt.defaults.exitcodes.EX_USAGE, exc.value
    assert "Usage" in exc.value.stderr, exc.value
    assert "no such option: --unknown-argument" in exc.value.stderr, exc.value


@slowTest
@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_exit_status_correct_usage(salt_factories, master_id):
    factory = salt_factories.get_salt_master_daemon(master_id)
    factory.start()
    assert factory.is_running()
    time.sleep(0.5)
    ret = factory.terminate()
    assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret
