import pytest

import salt.utils.data
import salt.utils.reactor as reactor
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def minion_reactor(minion_opts):
    return reactor.Reactor(minion_opts)


@pytest.fixture
def master_reactor(master_opts):
    return reactor.Reactor(master_opts)


@pytest.mark.skip_on_windows(reason="Reactors unavailable on Windows")
def test_run_minion_reactor(minion_opts, minion_reactor):
    """
    Ensure that list_reactors() returns the correct list of reactor SLS
    files for each tag.
    """

    with patch.object(salt.utils.event, "get_event", MagicMock()):
        os_nice_mock = MagicMock(return_value=True)
        with patch("os.nice", os_nice_mock):
            # By default os.nice should not be called
            minion_reactor.run()
            assert os_nice_mock.mock_calls == []

            # if reactor_niceness is set, os.nice should be called with that value
            with patch.dict(minion_opts, {"reactor_niceness": 9}):
                minion_reactor.run()
                calls = [call(9)]
                os_nice_mock.assert_has_calls(calls)


@pytest.mark.skip_on_windows(reason="Reactors unavailable on Windows")
def test_run_master_reactor(master_opts, master_reactor):
    """
    Ensure that list_reactors() returns the correct list of reactor SLS
    files for each tag.
    """

    with patch.object(salt.utils.event, "get_event", MagicMock()):
        os_nice_mock = MagicMock(return_value=True)
        with patch("os.nice", os_nice_mock):
            # By default os.nice should not be called
            master_reactor.run()
            assert os_nice_mock.mock_calls == []

            # if reactor_niceness is set, os.nice should be called with that value
            with patch.dict(master_opts, {"reactor_niceness": 9}):
                master_reactor.run()
                calls = [call(9)]
                os_nice_mock.assert_has_calls(calls)
