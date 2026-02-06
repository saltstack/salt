"""
    Unit tests for the salt.modules.state module
"""

import pytest

import salt.loader.context
import salt.modules.config as config
import salt.modules.state as state
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        state: {"__salt__": {"config.get": config.get}, "__opts__": {"test": True}},
        config: {"__opts__": {}},
    }


def test_get_initial_pillar():
    """
    _get_initial_pillar returns pillar data not named context
    """
    ctx = salt.loader.context.LoaderContext()
    pillar_data = {"foo": "bar"}
    named_ctx = ctx.named_context("__pillar__", pillar_data)
    opts = {"__cli": "salt-call", "pillarenv": "base"}
    with patch("salt.modules.state.__pillar__", named_ctx, create=True):
        with patch("salt.modules.state.__opts__", opts, create=True):
            pillar = state._get_initial_pillar(opts)
            assert pillar == pillar_data


def test_check_test_value_is_boolean():
    """
    Ensure that the test value is always returned as a boolean
    """
    with patch.dict(state.__opts__, {"test": True}, create=True):
        assert state._get_test_value() is True
        assert state._get_test_value(True) is True
        assert state._get_test_value(False) is False
        assert state._get_test_value("test") is True
        assert state._get_test_value(123) is True

    with patch.dict(state.__opts__, {"test": False}, create=True):
        assert state._get_test_value() is False


def test_prior_running_states_checks_flags():
    """
    Test that _prior_running_states correctly handles newer JIDs
    by checking for the queue flag.
    """
    # Setup
    my_jid = 100
    newer_jid = 101

    # Mock __opts__ needed for cachedir
    opts = {"cachedir": "/tmp/salt_test_cache"}

    # Mock is_running to return the newer JID
    active_jobs = [{"jid": str(newer_jid), "pid": 1234, "fun": "state.apply"}]

    with patch.dict(state.__opts__, opts, create=True), patch(
        "salt.modules.state.__salt__",
        {"saltutil.is_running": MagicMock(return_value=active_jobs)},
    ), patch("os.path.exists") as mock_exists, patch("os.listdir") as mock_listdir:

        # Case 1: Newer JID has a flag (it is starting/waiting).
        # We should IGNORE it (return empty list).

        # Logic:
        # 1. os.path.exists(queue_dir) -> True (for checking state_queue presence)
        # 2. os.listdir -> [] (empty state_queue for this test part, or we just ignore duplicates)
        # 3. loop active_jobs
        # 4. newer > my.
        # 5. queue_path = .../101
        # 6. os.path.exists(queue_path) -> True (Flag exists)

        def side_effect_exists(path):
            if "state_queue" in path and str(newer_jid) in path:
                return True  # Flag exists
            if path.endswith("state_queue"):
                return True  # Dir exists
            return False

        mock_exists.side_effect = side_effect_exists
        mock_listdir.return_value = []  # Nothing extra in queue dir

        ret = state._prior_running_states(str(my_jid))
        assert len(ret) == 0

        # Case 2: Newer JID has NO flag (it is running).
        # We should WAIT for it (return it in the list).

        def side_effect_exists_no_flag(path):
            if "state_queue" in path and str(newer_jid) in path:
                return False  # Flag GONE
            if path.endswith("state_queue"):
                return True
            return False

        mock_exists.side_effect = side_effect_exists_no_flag

        ret = state._prior_running_states(str(my_jid))
        assert len(ret) == 1
        assert ret[0]["jid"] == str(newer_jid)


def test_prior_running_states_checks_state_queue():
    """
    Test that _prior_running_states checks state_queue for invisible jobs.
    """
    my_jid = 101
    older_jid = 100

    opts = {"cachedir": "/tmp/salt_test_cache"}

    # is_running returns NOTHING (Invisible Gap)
    active_jobs = []

    with patch.dict(state.__opts__, opts, create=True), patch(
        "salt.modules.state.__salt__",
        {"saltutil.is_running": MagicMock(return_value=active_jobs)},
    ), patch("os.path.exists") as mock_exists, patch(
        "os.listdir"
    ) as mock_listdir, patch(
        "salt.utils.files.fopen", MagicMock()
    ) as mock_fopen, patch(
        "salt.utils.process.os_is_running", MagicMock(return_value=True)
    ):

        # mock_exists for queue_dir -> True
        mock_exists.return_value = True
        # mock_listdir returns [older_jid]
        mock_listdir.return_value = [str(older_jid)]

        # Setup mock_fopen to return a context manager that returns a file object with read() returning "1234"
        mock_file = MagicMock()
        mock_file.read.return_value = "1234"
        mock_fopen.return_value.__enter__.return_value = mock_file

        # Verify my_jid (101) sees older_jid (100)
        ret = state._prior_running_states(str(my_jid))

        assert len(ret) == 1
        assert ret[0]["jid"] == str(older_jid)
