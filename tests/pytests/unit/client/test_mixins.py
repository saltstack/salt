"""
Tests for salt.client.mixins
"""

import pytest

import salt.runner
from tests.support.mock import MagicMock, patch


@pytest.fixture
def runner_client(master_opts):
    return salt.runner.RunnerClient(master_opts)


def test_low_early_failure_is_returned_not_masked(runner_client):
    """
    An exception raised before the proc file is written (here: an unknown
    function rejected by ``verify_fun``) must be captured and returned by
    ``low()``, not replaced by an ``UnboundLocalError`` on ``proc_fn`` from
    the ``finally`` cleanup.
    """
    with patch("salt.utils.event.get_event", MagicMock()), patch(
        "salt.utils.job.store_job", MagicMock()
    ) as store_job:
        ret = runner_client.low(
            "nonexistent.function",
            {"fun": "nonexistent.function"},
            print_event=False,
            full_return=True,
        )

    assert ret["success"] is False
    assert ret["retcode"] == 1
    assert "'nonexistent.function' is not available" in ret["return"]
    store_job.assert_called_once()
