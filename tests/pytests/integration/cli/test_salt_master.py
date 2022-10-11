import logging
import time

import pytest
from saltfactories.utils import random_string

import salt.defaults.exitcodes
from tests.support.helpers import PRE_PYTEST_SKIP_REASON

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
]

log = logging.getLogger(__name__)


@pytest.fixture
def master_id():
    return random_string("master-")


@pytest.mark.skip_on_windows(reason=PRE_PYTEST_SKIP_REASON)
def test_exit_status_correct_usage(salt_factories, master_id):
    factory = salt_factories.salt_master_daemon(master_id)
    factory.start()
    assert factory.is_running()
    time.sleep(0.5)
    ret = factory.terminate()
    assert ret.returncode == salt.defaults.exitcodes.EX_OK, ret
