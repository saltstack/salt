"""
    Unit tests for the salt.modules.state module
"""

import pytest

import salt.loader.context
import salt.modules.config as config
import salt.modules.state as state
import salt.payload
import salt.utils.files
import salt.utils.state
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {
        state: {
            "__salt__": {
                "config.get": config.get,
                "saltutil.is_running": MagicMock(return_value=[]),
            },
            "__opts__": {"test": True, "cachedir": "/tmp/salt_test_cache"},
        },
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


def test_check_queue_queues_job_when_conflict():
    """
    Test that _check_queue serializes the job and returns queued=True when prior states exist.
    """
    my_jid = "20230101000000100000"
    older_jid = "20230101000000000000"
    new_jid = "20230101000000300000"

    kwargs = {
        "__pub_jid": my_jid,
        "__pub_fun": "state.apply",
        "__pub_arg": ["foo"],
        "__pub_tgt": "*",
        "__pub_ret": "",
        "__pub_user": "root",
        "concurrent": False,
    }

    # Mock active jobs containing an older job
    active_jobs = [{"jid": older_jid, "pid": 1234, "fun": "state.apply"}]

    opts = {"cachedir": "/tmp/salt_test_cache"}

    # Mock the lock to do nothing
    mock_lock = MagicMock()
    mock_lock.__enter__ = MagicMock(return_value=None)
    mock_lock.__exit__ = MagicMock(return_value=None)

    with patch.dict(state.__opts__, opts, create=True), patch(
        "salt.modules.state.__salt__",
        {"saltutil.is_running": MagicMock(return_value=active_jobs)},
    ), patch("salt.utils.state.acquire_queue_lock", return_value=mock_lock), patch(
        "os.path.exists", return_value=True
    ), patch(
        "os.listdir", return_value=[]
    ), patch(
        "salt.utils.jid.gen_jid", return_value=new_jid
    ), patch(
        "salt.utils.files.fopen", mock_open()
    ) as mock_file, patch(
        "salt.payload.dump"
    ) as mock_dump, patch(
        "salt.utils.atomicfile.atomic_rename"
    ) as mock_rename:

        ret = state._check_queue(True, kwargs)

        # Should return queued dict
        assert isinstance(ret, dict)
        assert ret["queued"] is True
        assert ret["result"] is True
        assert "Job queued for execution" in ret["comment"]

        # Should have dumped payload
        assert mock_dump.called
        args, _ = mock_dump.call_args
        payload = args[0]
        assert payload["jid"] == new_jid
        assert payload["fun"] == "state.apply"


def test_check_queue_proceeds_when_no_conflict():
    """
    Test that _check_queue returns None (proceeds) when no prior states exist.
    """
    my_jid = "20230101000000100000"

    kwargs = {"__pub_jid": my_jid, "concurrent": False}

    # Mock active jobs - EMPTY
    active_jobs = []

    opts = {"cachedir": "/tmp/salt_test_cache"}

    mock_lock = MagicMock()
    mock_lock.__enter__ = MagicMock(return_value=None)
    mock_lock.__exit__ = MagicMock(return_value=None)

    with patch.dict(state.__opts__, opts, create=True), patch(
        "salt.modules.state.__salt__",
        {"saltutil.is_running": MagicMock(return_value=active_jobs)},
    ), patch("salt.utils.state.acquire_queue_lock", return_value=mock_lock), patch(
        "os.path.exists", return_value=False
    ):  # No queue dir

        ret = state._check_queue(True, kwargs)

        # Should return None (no conflict)
        assert ret is None


def test_check_queue_detects_queued_file_as_conflict():
    """
    Test that _check_queue sees a file in state_queue as a conflict and queues itself.
    """
    my_jid = "20230101000000200000"
    older_queued_jid = "20230101000000100000"

    kwargs = {"__pub_jid": my_jid, "__pub_fun": "state.apply", "concurrent": False}

    # Mock active jobs - EMPTY (simulating gap where job is only on disk)
    active_jobs = []

    opts = {"cachedir": "/tmp/salt_test_cache"}

    mock_lock = MagicMock()
    mock_lock.__enter__ = MagicMock(return_value=None)
    mock_lock.__exit__ = MagicMock(return_value=None)

    # Mock os.listdir to return an older queued file
    queued_filename = f"queued_123456_{older_queued_jid}.p"

    with patch.dict(state.__opts__, opts, create=True), patch(
        "salt.modules.state.__salt__",
        {"saltutil.is_running": MagicMock(return_value=active_jobs)},
    ), patch("salt.utils.state.acquire_queue_lock", return_value=mock_lock), patch(
        "os.path.exists", return_value=True
    ), patch(
        "os.listdir", return_value=[queued_filename]
    ), patch(
        "salt.utils.files.fopen", mock_open()
    ) as mock_file, patch(
        "salt.payload.dump"
    ) as mock_dump, patch(
        "salt.utils.atomicfile.atomic_rename"
    ) as mock_rename:

        ret = state._check_queue(True, kwargs)

        # Should return queued dict because it saw the older queued file
        assert isinstance(ret, dict)
        assert ret["queued"] is True
        assert ret["result"] is True

        # Should have dumped payload
        assert mock_dump.called
