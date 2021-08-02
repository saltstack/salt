import logging

import pytest
import salt.defaults.exitcodes
from saltfactories.exceptions import FactoryNotStarted
from saltfactories.utils import random_string

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]

log = logging.getLogger(__name__)


@pytest.fixture
def master_id():
    return random_string("master-")


@pytest.mark.skip_on_windows(reason="Windows does not do user checks")
def test_exit_status_unknown_user(salt_factories, master_id):
    """
    Ensure correct exit status when the master is configured to run as an unknown user.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_factories.salt_master_daemon(
            master_id, overrides={"user": "unknown-user"}
        )
        with factory.started(start_timeout=10, max_start_attempts=1):
            # We should not get here
            pass

    assert exc.value.exitcode == salt.defaults.exitcodes.EX_NOUSER, exc.value
    assert "The user is not available." in exc.value.stderr, exc.value


def test_exit_status_unknown_argument(salt_factories, master_id):
    """
    Ensure correct exit status when an unknown argument is passed to salt-master.
    """
    with pytest.raises(FactoryNotStarted) as exc:
        factory = salt_factories.salt_master_daemon(master_id)
        factory.start("--unknown-argument", start_timeout=10, max_start_attempts=1)
    assert exc.value.exitcode == salt.defaults.exitcodes.EX_USAGE, exc.value
    assert "Usage" in exc.value.stderr, exc.value
    assert "no such option: --unknown-argument" in exc.value.stderr, exc.value
