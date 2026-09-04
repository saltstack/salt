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

    Regression test for #69386: when the master has already assigned a JID
    (the normal publish path), the queued payload must retain that JID rather
    than be re-stamped with a freshly-minted one. Job-tracking infrastructure
    (returners, jobs runner, syndic) relies on the published JID being the
    one the minion executes under.
    """
    my_jid = "20230101000000100000"
    older_jid = "20230101000000000000"
    # This is the JID gen_jid would mint if the code wrongly fell through to
    # the salt-call branch. The fix means we must NOT see this value land in
    # either the payload or the queue filename when __pub_jid is present.
    bogus_minted_jid = "20230101000000300000"

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

    opts = {"cachedir": "/tmp/salt_test_cache", "master": "master-a"}

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
        "salt.utils.jid.gen_jid", return_value=bogus_minted_jid
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
        # The master-assigned JID must be preserved end-to-end.
        assert payload["jid"] == my_jid
        assert payload["jid"] != bogus_minted_jid
        assert payload["fun"] == "state.apply"

        # The queue file must land under the per-master state_queue dir.
        expected_dir = salt.utils.state.state_queue_dir(opts)
        rename_args, _ = mock_rename.call_args
        # atomic_rename(tmp_path, final_path)
        final_path = rename_args[1]
        assert final_path.startswith(expected_dir), final_path
        # Filename pattern is queued_<microseconds>_<jid>.p — the JID embedded
        # in the filename must also be the master JID so the drain side
        # observes consistent ordering with what was published.
        assert final_path.endswith(f"_{my_jid}.p"), final_path


def test_check_queue_preserves_master_jid_69386():
    """
    Regression test for #69386: queued state runs must NOT mint a new JID
    when the master already assigned one via ``__pub_jid``.

    Before the fix, ``_check_queue`` called ``salt.utils.jid.gen_jid()``
    unconditionally and wrote the resulting JID into both the payload and
    the queue filename, breaking master-side job tracking (the master saw
    the original published JID; the minion executed under a different one,
    so returns came back tagged with a JID the master never published).
    """
    master_jid = "20260601000000123456"
    older_jid = "20260601000000000001"
    must_not_appear = "99999999999999999999"

    kwargs = {
        "__pub_jid": master_jid,
        "__pub_fun": "state.apply",
        "__pub_arg": ["highstate"],
        "__pub_tgt": "minion-1",
        "__pub_ret": "",
        "__pub_user": "root",
        "concurrent": False,
    }

    active_jobs = [{"jid": older_jid, "pid": 4321, "fun": "state.apply"}]
    opts = {"cachedir": "/tmp/salt_test_cache", "master": "master-a"}

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
        "salt.utils.jid.gen_jid", return_value=must_not_appear
    ) as mock_gen_jid, patch(
        "salt.utils.files.fopen", mock_open()
    ), patch(
        "salt.payload.dump"
    ) as mock_dump, patch(
        "salt.utils.atomicfile.atomic_rename"
    ) as mock_rename:

        ret = state._check_queue(True, kwargs)

        assert isinstance(ret, dict) and ret.get("queued") is True

        # gen_jid must NOT be called when __pub_jid is present.
        assert not mock_gen_jid.called, (
            "gen_jid was called even though the master supplied __pub_jid; "
            "this is the #69386 regression"
        )

        args, _ = mock_dump.call_args
        payload = args[0]
        assert payload["jid"] == master_jid

        rename_args, _ = mock_rename.call_args
        final_path = rename_args[1]
        assert final_path.endswith(f"_{master_jid}.p"), final_path


def test_check_queue_mints_jid_for_saltcall_when_no_pub_jid():
    """
    Companion to #69386: in the salt-call path the master never assigns a
    JID, so the minion must still mint one for the queued payload — but
    only in that case.
    """
    minted = "20260601000000777777"
    older_jid = "20260601000000000001"

    # No __pub_jid at all — simulates salt-call.
    kwargs = {
        "__pub_fun": "state.apply",
        "__pub_arg": ["highstate"],
        "__pub_tgt": "*",
        "__pub_ret": "",
        "__pub_user": "root",
        "concurrent": False,
    }

    active_jobs = [{"jid": older_jid, "pid": 4321, "fun": "state.apply"}]
    opts = {"cachedir": "/tmp/salt_test_cache", "master": "master-a"}

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
        "salt.utils.jid.gen_jid", return_value=minted
    ) as mock_gen_jid, patch(
        "salt.utils.files.fopen", mock_open()
    ), patch(
        "salt.payload.dump"
    ) as mock_dump, patch(
        "salt.utils.atomicfile.atomic_rename"
    ) as mock_rename:

        ret = state._check_queue(True, kwargs)

        assert isinstance(ret, dict) and ret.get("queued") is True
        assert (
            mock_gen_jid.called
        ), "gen_jid must be called when no master JID is available"

        args, _ = mock_dump.call_args
        payload = args[0]
        assert payload["jid"] == minted

        rename_args, _ = mock_rename.call_args
        final_path = rename_args[1]
        assert final_path.endswith(f"_{minted}.p"), final_path


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


def test_event_handles_binary_payload(tmp_path):
    """
    state.event must not abort with UnicodeDecodeError when an event payload
    contains arbitrary binary bytes (e.g. the DER-encoded certificate returned
    by x509.sign_remote_certificate).

    Regression test for #68411.
    """
    import json as _json

    # A snippet of real DER-encoded cert bytes that cannot be UTF-8 decoded.
    binary_payload = b"0\x82\x04\x8c\x82\x18\xb0"
    fake_event = {
        "tag": "salt/job/20251020115221844441/ret/localhost",
        "data": {
            "fun": "x509.sign_remote_certificate",
            "return": {
                "data": {"signing_cert": binary_payload},
                "errors": [],
            },
        },
    }

    captured = []

    class _FakeEvent:
        def __init__(self, *args, **kwargs):
            self._delivered = False

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_event(self, *args, **kwargs):
            if self._delivered:
                return None
            self._delivered = True
            return fake_event

    def _capture(msg):
        captured.append(msg)

    with patch("salt.utils.event.get_event", _FakeEvent), patch(
        "salt.utils.stringutils.print_cli", _capture
    ), patch.dict(state.__opts__, {"sock_dir": str(tmp_path)}, create=True):
        # count=1 so the loop exits after the single matched event.
        state.event(tagmatch="*", count=1, quiet=False)

    assert captured, "state.event did not emit the binary-payload event"
    line = captured[0]
    tag, _, body = line.partition("\t")
    assert tag == fake_event["tag"]
    parsed = _json.loads(body)
    assert parsed["fun"] == "x509.sign_remote_certificate"
