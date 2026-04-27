"""
Direct unit tests for the non-``progress_batch`` helpers in
``salt.utils.batch_state``.

The conformance scenarios in :mod:`.test_conformance` cover the state
machine itself.  These tests pin the surrounding helpers:
``get_batch_size``, ``create_batch_state``, ``is_batch_done``, and the
``.batch.p`` / ``batch_active.p`` persistence functions.
"""

import pytest

import salt.exceptions
from salt.utils.batch_state import (
    add_to_active_index,
    create_batch_state,
    get_batch_size,
    is_batch_done,
    read_active_index,
    read_batch_state,
    remove_from_active_index,
    write_active_index,
    write_batch_state,
)

# ---------------------------------------------------------------------------
# get_batch_size
# ---------------------------------------------------------------------------


class TestGetBatchSize:
    def test_integer_spec(self):
        assert get_batch_size(10, 100) == 10

    def test_integer_string_spec(self):
        assert get_batch_size("10", 100) == 10

    def test_percentage_25(self):
        assert get_batch_size("25%", 100) == 25

    def test_percentage_100_exact(self):
        assert get_batch_size("100%", 5) == 5

    def test_percentage_rounds_up_below_one(self):
        # 1% of 50 = 0.5, must round up to 1.
        assert get_batch_size("1%", 50) == 1

    def test_percentage_fractional_truncates_when_above_one(self):
        # 33% of 10 = 3.3, sync batch floors via int().
        assert get_batch_size("33%", 10) == 3

    def test_zero_batch_floors_to_one(self):
        # Zero would deadlock the state machine; floor to 1.
        assert get_batch_size(0, 100) == 1

    def test_negative_batch_floors_to_one(self):
        assert get_batch_size(-5, 100) == 1

    def test_empty_minion_list_returns_at_least_one(self):
        assert get_batch_size("50%", 0) == 1

    def test_invalid_string_raises_invocation_error(self):
        with pytest.raises(salt.exceptions.SaltInvocationError):
            get_batch_size("not-a-number", 10)

    def test_none_raises_invocation_error(self):
        with pytest.raises(salt.exceptions.SaltInvocationError):
            get_batch_size(None, 10)


# ---------------------------------------------------------------------------
# create_batch_state
# ---------------------------------------------------------------------------


class TestCreateBatchState:
    def test_populates_required_fields(self):
        opts = {
            "batch": 2,
            "fun": "test.ping",
            "arg": [],
            "tgt": "*",
            "tgt_type": "glob",
            "timeout": 30,
            "gather_job_timeout": 5,
        }
        state = create_batch_state(opts, ["m1", "m2", "m3"], "JID1", now=100.0)
        assert state["jid"] == "JID1"
        assert state["all_minions"] == ["m1", "m2", "m3"]
        assert state["pending"] == ["m1", "m2", "m3"]
        assert state["active"] == {}
        assert state["done"] == {}
        assert state["failed"] == {}
        assert state["wait"] == []
        assert state["batch_size"] == 2
        assert state["fun"] == "test.ping"
        assert state["tgt"] == "*"
        assert state["tgt_type"] == "glob"
        assert state["timeout"] == 30
        assert state["gather_job_timeout"] == 5
        assert state["created"] == 100.0
        assert state["last_progress"] == 100.0
        assert state["halted"] is False
        assert state["halted_reason"] is None
        assert state["driver"] == "cli"

    def test_percentage_batch_spec(self):
        state = create_batch_state(
            {"batch": "50%"}, ["m1", "m2", "m3", "m4"], "JID", now=1.0
        )
        assert state["batch_size"] == 2

    def test_driver_defaults_cli_but_can_be_master(self):
        state = create_batch_state(
            {"batch": 1}, ["m1"], "JID", driver="master", now=1.0
        )
        assert state["driver"] == "master"

    def test_pending_is_copy_not_alias(self):
        # Mutating all_minions later must not bleed into pending.
        minions = ["m1", "m2"]
        state = create_batch_state({"batch": 1}, minions, "JID", now=1.0)
        minions.append("m3")
        assert state["pending"] == ["m1", "m2"]
        assert state["all_minions"] == ["m1", "m2"]

    def test_ret_falls_back_to_return(self):
        state = create_batch_state(
            {"batch": 1, "return": "slack"}, ["m1"], "JID", now=1.0
        )
        assert state["ret"] == "slack"

    def test_user_defaults_to_root(self):
        state = create_batch_state({"batch": 1}, ["m1"], "JID", now=1.0)
        assert state["user"] == "root"


# ---------------------------------------------------------------------------
# is_batch_done
# ---------------------------------------------------------------------------


class TestIsBatchDone:
    def test_drained_state_is_done(self):
        state = {"pending": [], "active": {}, "halted": False}
        assert is_batch_done(state) is True

    def test_halted_state_is_done(self):
        state = {"pending": ["m1"], "active": {"m2": 1}, "halted": True}
        assert is_batch_done(state) is True

    def test_pending_prevents_done(self):
        state = {"pending": ["m1"], "active": {}, "halted": False}
        assert is_batch_done(state) is False

    def test_active_prevents_done(self):
        state = {"pending": [], "active": {"m1": 1.0}, "halted": False}
        assert is_batch_done(state) is False


# ---------------------------------------------------------------------------
# Persistence helpers — .batch.p and batch_active.p
# ---------------------------------------------------------------------------


@pytest.fixture
def opts(tmp_path):
    return {
        "cachedir": str(tmp_path),
        "hash_type": "sha256",
    }


class TestBatchStatePersistence:
    def test_round_trip(self, opts):
        state = {
            "jid": "JID1",
            "pending": ["m1"],
            "done": {"m2": True},
            "halted": False,
        }
        write_batch_state("JID1", state, opts)
        assert read_batch_state("JID1", opts) == state

    def test_read_missing_returns_none(self, opts):
        assert read_batch_state("does-not-exist", opts) is None

    def test_read_corrupt_returns_none(self, opts, tmp_path):
        # Write garbage to the expected location.
        write_batch_state("JID", {"ok": True}, opts)
        # Overwrite with non-msgpack bytes.
        import salt.utils.files
        from salt.utils.batch_state import _batch_state_path

        path = _batch_state_path("JID", opts)
        with salt.utils.files.fopen(path, "wb") as fp:
            fp.write(b"\xff\xff\xff\xff not msgpack \xff\xff")
        assert read_batch_state("JID", opts) is None


class TestActiveIndexPersistence:
    def test_round_trip_set(self, opts):
        write_active_index({"JID1", "JID2"}, opts)
        assert read_active_index(opts) == {"JID1", "JID2"}

    def test_read_missing_returns_empty_set(self, opts):
        assert read_active_index(opts) == set()

    def test_add_and_remove(self, opts):
        add_to_active_index("JID1", opts)
        add_to_active_index("JID2", opts)
        assert read_active_index(opts) == {"JID1", "JID2"}

        remove_from_active_index("JID1", opts)
        assert read_active_index(opts) == {"JID2"}

    def test_remove_missing_is_noop(self, opts):
        add_to_active_index("JID1", opts)
        remove_from_active_index("JID-does-not-exist", opts)
        assert read_active_index(opts) == {"JID1"}
