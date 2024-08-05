import threading

import pytest

import salt.utils.data
import salt.utils.event
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


@pytest.mark.skip_on_windows(reason="Reactors unavailable on Windows")
def test_reactors_list_in_separate_thread(master_opts, master_reactor):
    """
    Test that some of the tasks for reactors are performed in the separate thread
    """

    list_reactors_thread_id = None
    get_reactions_thread_id = None

    def list_reactors(*args, **kwargs):
        nonlocal list_reactors_thread_id
        list_reactors_thread_id = threading.get_ident()
        return ["test_reactor"]

    def get_reactions(*args, **kwargs):
        nonlocal get_reactions_thread_id
        get_reactions_thread_id = threading.get_ident()
        return []

    with patch.object(
        salt.utils.event.SaltEvent,
        "iter_events",
        return_value=iter([{"tag": "test", "data": {}}]),
    ), patch.object(master_reactor, "list_reactors", list_reactors), patch.object(
        master_reactor, "reactions", get_reactions
    ):
        main_thread_id = threading.get_ident()
        master_reactor.run()
        assert main_thread_id != list_reactors_thread_id
        assert main_thread_id != get_reactions_thread_id
        assert list_reactors_thread_id == get_reactions_thread_id
        assert None not in (list_reactors_thread_id, get_reactions_thread_id)
