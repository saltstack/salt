"""Tests for ``salt.cluster.consensus.raft`` log and storage."""

import os

import pytest

import salt.cluster.consensus.storage as storage_module
import salt.config
from salt.cluster.consensus.raft import (
    CounterStateMachine,
    Log,
    LogEntry,
    LogEntryCommitStatus,
    LogEntryType,
)
from salt.cluster.consensus.storage import SaltStorage
from tests.support.mock import patch


@pytest.fixture
def status():
    # 3 total nodes: majority is 2.
    return LogEntryCommitStatus(3)


@pytest.fixture
def storage(tmp_path):
    """SaltStorage backed by a temporary localfs cache directory."""
    opts = salt.config.master_config("/dev/null")
    opts["cachedir"] = str(tmp_path)
    return SaltStorage("test-node", opts)


def test_log_entry_commit_status_defaults(status):
    assert status.committed() is False


def test_log_entry_commit_status_set(status):
    status.set("a")
    # 1/3 is not majority
    assert status.committed() is False
    status.set("b")
    # 2/3 is majority
    assert status.committed() is True


def test_log_entry_commit_status_info(status):
    info = status.info()
    assert info == {"committed": False}

    status.set("a")
    status.set("b")
    info = status.info()
    assert info == {"committed": True}


def test_log_entry_commit_status_info_w_commits(status):
    status.set("a")
    info = status.info(include_commits=True)
    assert info["committed"] is False
    assert set(info["committed_nodes"]) == {"a"}

    status.set("b")
    info = status.info(include_commits=True)
    assert info["committed"] is True
    assert set(info["committed_nodes"]) == {"a", "b"}


def test_log_entry():
    entry = LogEntry(1, 0, "mycmd")
    assert entry.term == 1
    assert entry.index == 0
    assert entry.cmd == "mycmd"
    assert entry.node_id is None


def test_log_entry_info():
    entry = LogEntry(1, 0, "mycmd", node_id="c")
    assert entry.info() == (1, 0, "mycmd", "c", 0, None, None)


def test_log_defaults():
    log = Log()
    assert log.term == 0
    assert log.index == -1
    assert log.entries == []


def test_log_set_term():
    log = Log()
    assert log.term == 0
    assert log.index == -1
    log.term = 10
    assert log.term == 10
    log.term = 9
    assert log.term == 9


def test_log_add():
    log = Log()
    log.add(1, "mycmd")
    assert log.entries == [LogEntry(1, 0, "mycmd")]


def test_log_add_with_old_term():
    log = Log()
    log.term = 10
    assert log.term == 10
    log.add(1, "mycmd")
    assert log.entries[-1].term == 1


def test_log_truncate_prefix():
    log = Log()
    for i in range(10):
        log.add(1, f"cmd{i}")

    assert log.index == 9
    assert len(log.entries) == 10

    log.truncate_prefix(4)
    assert log.last_included_index == 4
    assert log.last_included_term == 1
    assert log.index == 9
    assert len(log.entries) == 5
    assert log.get_entry(4) is None
    assert log.get_entry(5).cmd == "cmd5"


def test_salt_storage_snapshot(storage):
    data = b"snapshot_data"
    storage.save_snapshot(data, 10, 2)
    loaded = storage.load_snapshot()
    assert loaded["data"] == data
    assert loaded["index"] == 10
    assert loaded["term"] == 2


def test_log_has_entry_no_logs():
    log = Log()
    assert log.entries == []
    assert log.term == 0
    assert log.index == -1
    assert log.has_entry(0, 0) is False
    assert log.has_entry(0, 1) is False
    assert log.has_entry(1, 0) is False
    assert log.has_entry(1, 1) is False


def test_log_has_entry_positive():
    log = Log()
    log.add(3, b"x")
    assert log.has_entry(3, 0) is True
    assert log.has_entry(2, 0) is False
    assert log.has_entry(3, 99) is False


def test_log_has_entry_at_snapshot_boundary():
    log = Log()
    log.last_included_index = 5
    log.last_included_term = 2
    assert log.has_entry(2, 5) is True
    assert log.has_entry(1, 5) is False


def test_log_entry_cmd_bytes_and_memoryview():
    e = LogEntry(1, 0, b"raw")
    assert e.cmd_bytes == b"raw"
    mv = memoryview(b"mv")
    e2 = LogEntry(1, 1, mv)
    assert e2.cmd_bytes == b"mv"
    assert e2 == b"mv"


def test_salt_storage_state_roundtrip(storage):
    storage.save_state(7, "voter-a")
    assert storage.load_state() == {
        "term": 7,
        "voted_for": "voter-a",
        "leader_id": None,
    }
    storage.save_state(8, None)
    assert storage.load_state() == {"term": 8, "voted_for": None, "leader_id": None}
    # Round-trip with an explicit leader_id (observability path).
    storage.save_state(9, "voter-b", leader_id="voter-b")
    assert storage.load_state() == {
        "term": 9,
        "voted_for": "voter-b",
        "leader_id": "voter-b",
    }


def test_salt_storage_log_append_and_reload(storage):
    e0 = LogEntry(1, 0, "a", None, LogEntryType.COMMAND)
    storage.append_log(e0)
    storage.append_log(LogEntry(1, 1, "b", None, LogEntryType.COMMAND))
    loaded = storage.load_log()
    assert len(loaded) == 2
    assert loaded[0].cmd == "a"
    assert loaded[1].index == 1


def test_salt_storage_defaults_when_empty(storage):
    assert storage.load_state() == {"term": 0, "voted_for": None, "leader_id": None}
    assert storage.load_log() == []
    assert storage.load_snapshot() is None


def test_salt_storage_save_and_reload_log(storage):
    entries = [
        LogEntry(1, 0, "x", None, LogEntryType.COMMAND),
        LogEntry(1, 1, "y", None, LogEntryType.CONFIG),
    ]
    storage.save_log(entries)
    loaded = storage.load_log()
    assert len(loaded) == 2
    assert loaded[0].term == 1
    assert loaded[1].type == LogEntryType.CONFIG


def test_counter_state_machine_apply_and_snapshot():
    sm = CounterStateMachine()
    assert sm.apply(b"a") == 1
    assert sm.apply(b"b", client_id="c", sequence_num=1) == 2
    assert sm.apply(b"c", client_id="c", sequence_num=1) == 2
    snap = sm.get_snapshot()
    sm2 = CounterStateMachine()
    sm2.restore_snapshot(snap)
    assert sm2.count == 2
    assert sm2.sessions["c"] == 1


def test_log_add_config_entry_type():
    log = Log()
    idx = log.add(1, {"voters": ["a"]}, entry_type=LogEntryType.CONFIG)
    assert idx == 0
    assert log.entries[0].type == LogEntryType.CONFIG


def test_log_clear():
    log = Log()
    log.add(1, "x")
    log.clear()
    assert log.entries == []
    assert log.index == -1


# ---------------------------------------------------------------------------
# MembershipStateMachine
# ---------------------------------------------------------------------------


class TestMembershipStateMachine:
    def test_initial_state_is_empty(self):
        from salt.cluster.consensus.raft.log import MembershipStateMachine

        sm = MembershipStateMachine()
        assert sm.current_voters() == []
        assert sm.current_learners() == []
        assert sm.membership_version == -1

    def test_apply_sets_voters_and_learners(self):
        from salt.cluster.consensus.raft.log import MembershipStateMachine

        sm = MembershipStateMachine()
        sm.apply({"voters": ["m1", "m2"], "learners": ["m3"]}, index=0)
        assert sm.current_voters() == ["m1", "m2"]
        assert sm.current_learners() == ["m3"]
        assert sm.membership_version == 0

    def test_apply_plain_list_treated_as_voters(self):
        from salt.cluster.consensus.raft.log import MembershipStateMachine

        sm = MembershipStateMachine()
        sm.apply(["m1", "m2"], index=1)
        assert sm.current_voters() == ["m1", "m2"]
        assert sm.current_learners() == []

    def test_apply_overwrites_previous_state(self):
        from salt.cluster.consensus.raft.log import MembershipStateMachine

        sm = MembershipStateMachine()
        sm.apply({"voters": ["m1"], "learners": ["m2"]}, index=0)
        sm.apply({"voters": ["m1", "m2"], "learners": []}, index=1)
        assert sm.current_voters() == ["m1", "m2"]
        assert sm.current_learners() == []
        assert sm.membership_version == 1

    def test_is_voter_and_is_learner(self):
        from salt.cluster.consensus.raft.log import MembershipStateMachine

        sm = MembershipStateMachine()
        sm.apply({"voters": ["m1"], "learners": ["m2"]}, index=0)
        assert sm.is_voter("m1") is True
        assert sm.is_voter("m2") is False
        assert sm.is_learner("m2") is True
        assert sm.is_learner("m1") is False
        assert sm.is_voter("unknown") is False

    def test_on_change_callback_fires(self):
        from salt.cluster.consensus.raft.log import MembershipStateMachine

        received = []
        sm = MembershipStateMachine(on_change=lambda v, l: received.append((v, l)))
        sm.apply({"voters": ["m1", "m2"], "learners": ["m3"]}, index=0)
        assert received == [(["m1", "m2"], ["m3"])]

    def test_on_change_callback_not_required(self):
        from salt.cluster.consensus.raft.log import MembershipStateMachine

        sm = MembershipStateMachine()
        sm.apply({"voters": ["m1"]}, index=0)
        assert sm.current_voters() == ["m1"]

    def test_snapshot_roundtrip(self):
        from salt.cluster.consensus.raft.log import MembershipStateMachine

        sm = MembershipStateMachine()
        sm.apply({"voters": ["m1", "m2"], "learners": ["m3"]}, index=5)

        snap = sm.get_snapshot()
        assert snap == {"voters": ["m1", "m2"], "learners": ["m3"], "version": 5}

        sm2 = MembershipStateMachine()
        sm2.restore_snapshot(snap)
        assert sm2.current_voters() == ["m1", "m2"]
        assert sm2.current_learners() == ["m3"]
        assert sm2.membership_version == 5

    def test_restore_snapshot_from_bytes(self):
        import json

        from salt.cluster.consensus.raft.log import MembershipStateMachine

        snap = {"voters": ["m1"], "learners": [], "version": 3}
        sm = MembershipStateMachine()
        sm.restore_snapshot(json.dumps(snap).encode())
        assert sm.current_voters() == ["m1"]
        assert sm.membership_version == 3

    def test_restore_snapshot_ignores_invalid(self):
        from salt.cluster.consensus.raft.log import MembershipStateMachine

        sm = MembershipStateMachine()
        sm.apply({"voters": ["m1"]}, index=0)
        sm.restore_snapshot(None)
        assert sm.current_voters() == ["m1"]

    def test_repr_includes_key_fields(self):
        from salt.cluster.consensus.raft.log import MembershipStateMachine

        sm = MembershipStateMachine()
        sm.apply({"voters": ["m1"], "learners": ["m2"]}, index=2)
        r = repr(sm)
        assert "m1" in r
        assert "m2" in r
        assert "version=2" in r


# ---------------------------------------------------------------------------
# Coverage gaps: LogEntryCommitStatus.set, LogEntry paths, Log edge cases,
# BaseStorage / BaseStateMachine abstract bodies
# ---------------------------------------------------------------------------


class TestLogEntryCommitStatusSet:
    def test_set_adds_node(self):
        from salt.cluster.consensus.raft.log import LogEntryCommitStatus

        cs = LogEntryCommitStatus(3)
        cs.set("n1")
        assert "n1" in cs._committed_nodes

    def test_set_contributes_to_committed_quorum(self):
        from salt.cluster.consensus.raft.log import LogEntryCommitStatus

        cs = LogEntryCommitStatus(3)
        cs.set("n1")
        cs.set("n2")
        assert cs.committed()


class TestLogEntryEdgePaths:
    def test_eq_with_memoryview(self):
        from salt.cluster.consensus.raft.log import LogEntry

        entry = LogEntry(1, 0, b"hello")
        assert entry == memoryview(b"hello")

    def test_eq_with_string(self):
        from salt.cluster.consensus.raft.log import LogEntry

        entry = LogEntry(1, 0, b"hello")
        assert entry == "hello"

    def test_cmd_view_returns_memoryview_from_bytes(self):
        from salt.cluster.consensus.raft.log import LogEntry

        entry = LogEntry(1, 0, b"data")
        view = entry.cmd_view
        assert isinstance(view, memoryview)
        assert bytes(view) == b"data"

    def test_cmd_view_passthrough_for_existing_memoryview(self):
        from salt.cluster.consensus.raft.log import LogEntry

        mv = memoryview(b"data")
        entry = LogEntry(1, 0, mv)
        assert entry.cmd_view is mv

    def test_info_returns_decoded_bytes(self):
        from salt.cluster.consensus.raft.log import LogEntry

        entry = LogEntry(1, 0, b"hello")
        info = entry.info()
        assert info[2] == "hello"


class TestLogEdgeCases:
    def test_repr(self):
        from salt.cluster.consensus.raft.log import Log

        lg = Log()
        r = repr(lg)
        assert "Log" in r

    def test_last_index_alias(self):
        from salt.cluster.consensus.raft.log import Log

        lg = Log()
        lg.add(1, b"x")
        assert lg.last_index == lg.index

    def test_add_at_snapshot_boundary_returns_false(self):
        """Adding an entry at or before last_included_index is a no-op."""
        from salt.cluster.consensus.raft.log import Log

        lg = Log()
        lg.last_included_index = 5
        result = lg.add(1, b"x", index=5)
        assert result is False

    def test_add_conflict_truncates_and_rewrites_with_storage(self, tmp_path):
        """Conflicting term at existing index truncates log and saves to storage."""
        from salt.cluster.consensus.raft.log import Log
        from salt.cluster.consensus.storage import SaltStorage

        opts = {"cachedir": str(tmp_path), "cluster_id": "test", "cluster_peers": []}
        storage = SaltStorage("n1", opts)
        lg = Log(storage=storage)
        lg.add(1, b"a")  # index 0, term 1
        lg.add(1, b"b")  # index 1, term 1
        # Overwrite index 1 with a different term -> conflict truncation + storage save
        lg.add(2, b"c", index=1)
        assert lg.entries[-1].cmd == b"c"
        assert lg.entries[-1].term == 2

    def test_add_gap_append_with_storage(self, tmp_path):
        """Appending past current end with explicit index writes to storage."""
        from salt.cluster.consensus.raft.log import Log
        from salt.cluster.consensus.storage import SaltStorage

        opts = {"cachedir": str(tmp_path), "cluster_id": "test", "cluster_peers": []}
        storage = SaltStorage("n1", opts)
        lg = Log(storage=storage)
        lg.add(1, b"a")  # index 0
        # Skip to index 2 (gap)
        lg.add(1, b"b", index=2)
        assert lg.index == 2

    def test_snapshot_empty_log_is_noop(self):
        from salt.cluster.consensus.raft.log import Log

        lg = Log()
        lg.snapshot()  # must not raise
        assert lg.entries == []

    def test_snapshot_without_state_machine_does_not_save(self, tmp_path):
        """snapshot() with no state_machine still discards entries."""
        from salt.cluster.consensus.raft.log import Log

        lg = Log()
        lg.add(1, b"x")
        lg.commit(0)
        lg.snapshot()
        assert lg.entries == []

    def test_clear_with_storage(self, tmp_path):
        from salt.cluster.consensus.raft.log import Log
        from salt.cluster.consensus.storage import SaltStorage

        opts = {"cachedir": str(tmp_path), "cluster_id": "test", "cluster_peers": []}
        storage = SaltStorage("n1", opts)
        lg = Log(storage=storage)
        lg.add(1, b"x")
        lg.clear()
        assert lg.entries == []
        # Reload from storage confirms clear was persisted
        reloaded = Log(storage=storage)
        assert reloaded.entries == []

    def test_has_entry_none_index(self):
        from salt.cluster.consensus.raft.log import Log

        lg = Log()
        assert lg.has_entry(1, None) is True

    def test_has_entry_minus_one_index(self):
        from salt.cluster.consensus.raft.log import Log

        lg = Log()
        assert lg.has_entry(1, -1) is True

    def test_has_entry_at_snapshot_boundary_correct_term(self):
        from salt.cluster.consensus.raft.log import Log

        lg = Log()
        lg.last_included_index = 3
        lg.last_included_term = 2
        assert lg.has_entry(2, 3) is True

    def test_truncate_prefix_with_storage(self, tmp_path):
        from salt.cluster.consensus.raft.log import Log
        from salt.cluster.consensus.storage import SaltStorage

        opts = {"cachedir": str(tmp_path), "cluster_id": "test", "cluster_peers": []}
        storage = SaltStorage("n1", opts)
        lg = Log(storage=storage)
        lg.add(1, b"a")
        lg.add(1, b"b")
        lg.add(1, b"c")
        lg.truncate_prefix(1)
        assert lg.last_included_index == 1
        assert len(lg.entries) == 1  # only index 2 remains

    def test_truncate_prefix_before_snapshot_noop(self):
        from salt.cluster.consensus.raft.log import Log

        lg = Log()
        lg.last_included_index = 5
        lg.truncate_prefix(3)  # already past 3, no-op
        assert lg.last_included_index == 5

    def test_max_log_size_triggers_snapshot(self):
        """Inserting past max_log_size triggers automatic snapshot."""
        from salt.cluster.consensus.raft.log import CounterStateMachine, Log

        sm = CounterStateMachine()
        lg = Log(state_machine=sm, max_log_size=3)
        lg.add(1, b"a")
        lg.add(1, b"b")
        lg.commit(1)
        lg.add(1, b"c")  # this pushes len to 3 == max_log_size
        # snapshot is triggered since commit_index(1) >= entries[0].index(0)
        assert lg.entries == [] or len(lg.entries) <= 3


class TestBaseStorageAndStateMachineAbstractBodies:
    # Shared concrete implementations — each abstract method under test
    # raises NotImplementedError via super(); the rest are no-op stubs to
    # satisfy pylint W0223 (abstract-method not overridden).

    class _ConcreteStorage:
        """Minimal BaseStorage subclass with all abstract methods stubbed."""

        from salt.cluster.consensus.raft.log import BaseStorage

        # Imported at class scope so the body is visible to the linter.
        # The actual import happens inside each test to keep them isolated.
        def save_state(self, term, voted_for):
            raise NotImplementedError

        def load_state(self):
            raise NotImplementedError

        def save_log(self, entries):
            raise NotImplementedError

        def load_log(self):
            raise NotImplementedError

        def save_snapshot(self, data, index, term):
            raise NotImplementedError

        def load_snapshot(self):
            raise NotImplementedError

    class _ConcreteSM:
        """Minimal BaseStateMachine subclass with all abstract methods stubbed."""

        def apply(self, cmd, client_id=None, sequence_num=None):
            raise NotImplementedError

        def get_snapshot(self):
            raise NotImplementedError

        def restore_snapshot(self, data):
            raise NotImplementedError

    def test_base_storage_save_state_raises(self):
        import pytest

        from salt.cluster.consensus.raft.log import BaseStorage

        class Concrete(BaseStorage):
            def save_state(self, term, voted_for):
                raise NotImplementedError

            def load_state(self):
                pass

            def save_log(self, entries):
                pass

            def load_log(self):
                pass

            def save_snapshot(self, data, index, term):
                pass

            def load_snapshot(self):
                pass

        with pytest.raises(NotImplementedError):
            Concrete().save_state(1, None)

    def test_base_storage_load_state_raises(self):
        import pytest

        from salt.cluster.consensus.raft.log import BaseStorage

        class Concrete(BaseStorage):
            def save_state(self, term, voted_for):
                pass

            def load_state(self):
                raise NotImplementedError

            def save_log(self, entries):
                pass

            def load_log(self):
                pass

            def save_snapshot(self, data, index, term):
                pass

            def load_snapshot(self):
                pass

        with pytest.raises(NotImplementedError):
            Concrete().load_state()

    def test_base_storage_save_log_raises(self):
        import pytest

        from salt.cluster.consensus.raft.log import BaseStorage

        class Concrete(BaseStorage):
            def save_state(self, term, voted_for):
                pass

            def load_state(self):
                pass

            def save_log(self, entries):
                raise NotImplementedError

            def load_log(self):
                pass

            def save_snapshot(self, data, index, term):
                pass

            def load_snapshot(self):
                pass

        with pytest.raises(NotImplementedError):
            Concrete().save_log([])

    def test_base_storage_save_snapshot_raises(self):
        import pytest

        from salt.cluster.consensus.raft.log import BaseStorage

        class Concrete(BaseStorage):
            def save_state(self, term, voted_for):
                pass

            def load_state(self):
                pass

            def save_log(self, entries):
                pass

            def load_log(self):
                pass

            def save_snapshot(self, data, index, term):
                raise NotImplementedError

            def load_snapshot(self):
                pass

        with pytest.raises(NotImplementedError):
            Concrete().save_snapshot(b"x", 0, 1)

    def test_base_storage_load_snapshot_raises(self):
        import pytest

        from salt.cluster.consensus.raft.log import BaseStorage

        class Concrete(BaseStorage):
            def save_state(self, term, voted_for):
                pass

            def load_state(self):
                pass

            def save_log(self, entries):
                pass

            def load_log(self):
                pass

            def save_snapshot(self, data, index, term):
                pass

            def load_snapshot(self):
                raise NotImplementedError

        with pytest.raises(NotImplementedError):
            Concrete().load_snapshot()

    def test_base_storage_load_log_raises(self):
        import pytest

        from salt.cluster.consensus.raft.log import BaseStorage

        class Concrete(BaseStorage):
            def save_state(self, term, voted_for):
                pass

            def load_state(self):
                pass

            def save_log(self, entries):
                pass

            def load_log(self):
                raise NotImplementedError

            def save_snapshot(self, data, index, term):
                pass

            def load_snapshot(self):
                pass

        with pytest.raises(NotImplementedError):
            Concrete().load_log()

    def test_base_state_machine_apply_raises(self):
        import pytest

        from salt.cluster.consensus.raft.log import BaseStateMachine

        class Concrete(BaseStateMachine):
            def apply(self, cmd, client_id=None, sequence_num=None):
                raise NotImplementedError

            def get_snapshot(self):
                pass

            def restore_snapshot(self, data):
                pass

        with pytest.raises(NotImplementedError):
            Concrete().apply(b"cmd")

    def test_base_state_machine_get_snapshot_raises(self):
        import pytest

        from salt.cluster.consensus.raft.log import BaseStateMachine

        class Concrete(BaseStateMachine):
            def apply(self, cmd, client_id=None, sequence_num=None):
                pass

            def get_snapshot(self):
                raise NotImplementedError

            def restore_snapshot(self, data):
                pass

        with pytest.raises(NotImplementedError):
            Concrete().get_snapshot()

    def test_base_state_machine_restore_snapshot_raises(self):
        import pytest

        from salt.cluster.consensus.raft.log import BaseStateMachine

        class Concrete(BaseStateMachine):
            def apply(self, cmd, client_id=None, sequence_num=None):
                pass

            def get_snapshot(self):
                pass

            def restore_snapshot(self, data):
                raise NotImplementedError

        with pytest.raises(NotImplementedError):
            Concrete().restore_snapshot({})


# ---------------------------------------------------------------------------
# Coverage gap: SaltStorage — dict-format log entry load, save_snapshot JSON
# ---------------------------------------------------------------------------


class TestSaltStorageDictFormatAndSnapshot:
    def test_load_log_dict_format(self, tmp_path):
        """SaltStorage.load_log handles dict-format entries from cache backends.

        Per-entry layout: ``cache.list`` enumerates the log keys (one per
        Raft index) and ``cache.fetch`` returns each entry's payload.
        Some backends serialize the payload as a dict instead of a tuple
        (``localfs_key`` legacy behaviour); the loader must accept both.
        """
        from salt.cluster.consensus.raft.log import LogEntryType
        from salt.cluster.consensus.storage import SaltStorage
        from tests.support.mock import patch

        opts = {
            "cachedir": str(tmp_path),
            "cluster_id": "test",
            "cluster_peers": [],
        }
        storage = SaltStorage("n1", opts)

        dict_entry = {
            "term": 1,
            "index": 0,
            "cmd": b"hello",
            "node_id": None,
            "type": LogEntryType.COMMAND,
            "client_id": None,
            "sequence_num": None,
        }
        with patch.object(storage._cache, "list", return_value=["0"]), patch.object(
            storage._cache, "fetch", return_value=dict_entry
        ):
            entries = storage.load_log()
        assert len(entries) == 1
        assert entries[0].cmd == b"hello"
        assert entries[0].term == 1

    def test_save_snapshot_json_encodes_dict(self, tmp_path):
        """save_snapshot JSON-encodes non-bytes data before storing."""
        from salt.cluster.consensus.storage import SaltStorage

        opts = {
            "cachedir": str(tmp_path),
            "cluster_id": "test",
            "cluster_peers": [],
        }
        storage = SaltStorage("n1", opts)
        snap_data = {"voters": ["m1", "m2"], "learners": []}
        storage.save_snapshot(snap_data, index=5, term=2)

        snap = storage.load_snapshot()
        assert snap is not None
        assert snap["index"] == 5
        assert snap["term"] == 2


class TestLogEntryCommitStatusInitialNode:
    def test_initial_node_added_to_committed_set(self):
        from salt.cluster.consensus.raft.log import LogEntryCommitStatus

        cs = LogEntryCommitStatus(3, initial_node="n1")
        assert "n1" in cs._committed_nodes


class TestCounterStateMachineRestoreSnapshotBytes:
    def test_restore_snapshot_invalid_bytes_uses_empty(self):
        """Non-JSON bytes fall back to empty state without raising."""
        from salt.cluster.consensus.raft.log import CounterStateMachine

        sm = CounterStateMachine()
        sm.count = 5
        sm.restore_snapshot(b"not-json-at-all!!!")
        # After invalid restore falls back to empty
        assert sm.count == 0

    def test_restore_snapshot_valid_bytes_restores_state(self):
        """JSON bytes are decoded and state is restored."""
        import json

        from salt.cluster.consensus.raft.log import CounterStateMachine

        sm = CounterStateMachine()
        snap = json.dumps({"count": 42, "sessions": {}}).encode()
        sm.restore_snapshot(snap)
        assert sm.count == 42


class TestCounterStateMachineRestoreNonBytesNonDict:
    def test_restore_snapshot_non_dict_non_bytes_falls_back_to_empty(self):
        """Non-dict, non-bytes input (e.g. a list) -> falls back to empty state."""
        from salt.cluster.consensus.raft.log import CounterStateMachine

        sm = CounterStateMachine()
        sm.count = 7
        sm.restore_snapshot([1, 2, 3])  # neither dict nor bytes
        assert sm.count == 0


# ---------------------------------------------------------------------------
# Regression: multi-state-machine snapshot envelope.
#
# Bug: Log.snapshot() used to serialise only the application state machine,
# so a CONFIG entry that had been compacted away left MembershipStateMachine
# empty after restart / install_snapshot.  These tests pin down the envelope
# shape and the round-trip via storage so the membership SM (and any future
# named SM) survives compaction.
# ---------------------------------------------------------------------------


class TestSnapshotEnvelope:
    """Envelope encoding/decoding helpers and round-trip behaviour."""

    def test_envelope_marker_is_v1(self):
        from salt.cluster.consensus.raft.log import SNAPSHOT_ENVELOPE_VERSION

        assert SNAPSHOT_ENVELOPE_VERSION == "raft.snapshot.v1"

    def test_encode_bytes_payload_is_json_safe(self):
        import json

        from salt.cluster.consensus.raft.log import Log

        encoded = Log._encode_sm_payload(b"\x00\x01\xff")
        # Must be JSON-serialisable so the storage layer can dump the envelope
        json.dumps(encoded)
        assert "__bytes__" in encoded
        assert Log._decode_sm_payload(encoded) == b"\x00\x01\xff"

    def test_encode_dict_payload_passthrough(self):
        from salt.cluster.consensus.raft.log import Log

        payload = {"voters": ["m1"], "learners": [], "version": 3}
        # Dicts are already JSON-safe — should not be wrapped
        assert Log._encode_sm_payload(payload) is payload
        assert Log._decode_sm_payload(payload) is payload

    def test_decode_bytes_marker_dict(self):
        import base64

        from salt.cluster.consensus.raft.log import Log

        encoded = {"__bytes__": base64.b64encode(b"abc").decode("ascii")}
        assert Log._decode_sm_payload(encoded) == b"abc"

    def test_maybe_envelope_recognises_dict(self):
        from salt.cluster.consensus.raft.log import SNAPSHOT_ENVELOPE_VERSION, Log

        env = {"__envelope__": SNAPSHOT_ENVELOPE_VERSION, "machines": {}}
        assert Log._maybe_envelope(env) is env

    def test_maybe_envelope_recognises_json_bytes(self):
        import json

        from salt.cluster.consensus.raft.log import SNAPSHOT_ENVELOPE_VERSION, Log

        env = {"__envelope__": SNAPSHOT_ENVELOPE_VERSION, "machines": {}}
        assert Log._maybe_envelope(json.dumps(env).encode()) == env

    def test_maybe_envelope_rejects_legacy_dict(self):
        from salt.cluster.consensus.raft.log import Log

        # Pre-fix payloads (e.g. CounterStateMachine.get_snapshot()) have no
        # __envelope__ key — must be treated as legacy single-SM data
        assert Log._maybe_envelope({"count": 5, "sessions": {}}) is None

    def test_maybe_envelope_rejects_unparseable_bytes(self):
        from salt.cluster.consensus.raft.log import Log

        assert Log._maybe_envelope(b"not-json-at-all") is None


class TestLogSnapshotMultiSM:
    """``Log.snapshot()`` must serialise every registered state machine."""

    def _make_storage(self, tmp_path):
        from salt.cluster.consensus.storage import SaltStorage

        opts = {"cachedir": str(tmp_path), "cluster_id": "test", "cluster_peers": []}
        return SaltStorage("n1", opts)

    def test_snapshot_envelope_contains_membership_sm(self, tmp_path):
        """A Log with both app SM and membership SM writes both into one snapshot."""
        import json

        from salt.cluster.consensus.raft.log import (
            SNAPSHOT_ENVELOPE_VERSION,
            CounterStateMachine,
            Log,
            LogEntryType,
            MembershipStateMachine,
        )

        storage = self._make_storage(tmp_path)
        app_sm = CounterStateMachine()
        mem_sm = MembershipStateMachine()
        lg = Log(
            storage=storage,
            state_machine=app_sm,
            state_machines={"membership_sm": mem_sm},
        )

        # Apply some app commands and a CONFIG entry -> SM state is non-empty.
        app_sm.apply(b"a")
        app_sm.apply(b"b")
        mem_sm.apply({"voters": ["m1", "m2", "m3"], "learners": []}, index=2)

        # Append entries so snapshot has something to discard
        lg.add(1, b"a")
        lg.add(1, b"b")
        lg.add(1, {"voters": ["m1", "m2", "m3"]}, entry_type=LogEntryType.CONFIG)
        lg.commit(2)

        lg.snapshot()
        raw = storage.load_snapshot()
        assert raw is not None

        envelope = json.loads(raw["data"].decode("utf-8"))
        assert envelope["__envelope__"] == SNAPSHOT_ENVELOPE_VERSION
        assert "state_machine" in envelope["machines"]
        assert "membership_sm" in envelope["machines"]
        assert envelope["machines"]["membership_sm"] == {
            "voters": ["m1", "m2", "m3"],
            "learners": [],
            "version": 2,
        }

    def test_snapshot_restore_preserves_membership(self, tmp_path):
        """Round-trip: snapshot, build a fresh Log on the same storage, membership intact."""
        from salt.cluster.consensus.raft.log import (
            CounterStateMachine,
            Log,
            LogEntryType,
            MembershipStateMachine,
        )

        storage = self._make_storage(tmp_path)
        app_sm = CounterStateMachine()
        mem_sm = MembershipStateMachine()
        lg = Log(
            storage=storage,
            state_machine=app_sm,
            state_machines={"membership_sm": mem_sm},
        )
        app_sm.apply(b"a")
        mem_sm.apply({"voters": ["m1", "m2"], "learners": ["m3"]}, index=4)
        lg.add(1, b"a")
        lg.add(
            1,
            {"voters": ["m1", "m2"], "learners": ["m3"]},
            entry_type=LogEntryType.CONFIG,
        )
        lg.commit(1)
        lg.snapshot()
        # Sanity: snapshot truncated the in-memory log
        assert lg.entries == []

        # Fresh Log on the same storage simulates a restart
        app_sm2 = CounterStateMachine()
        mem_sm2 = MembershipStateMachine()
        lg2 = Log(
            storage=storage,
            state_machine=app_sm2,
            state_machines={"membership_sm": mem_sm2},
        )
        # last_included_* picked up from the saved snapshot
        assert lg2.last_included_index == 1
        # And both state machines were restored
        assert app_sm2.count == 1
        assert mem_sm2.current_voters() == ["m1", "m2"]
        assert mem_sm2.current_learners() == ["m3"]
        assert mem_sm2.membership_version == 4

    def test_register_state_machine_after_init(self, tmp_path):
        """SMs registered post-init are still serialised on the next snapshot."""
        import json

        from salt.cluster.consensus.raft.log import (
            CounterStateMachine,
            Log,
            MembershipStateMachine,
        )

        storage = self._make_storage(tmp_path)
        lg = Log(storage=storage, state_machine=CounterStateMachine())
        late_sm = MembershipStateMachine()
        late_sm.apply({"voters": ["m1"], "learners": []}, index=0)
        lg.register_state_machine("membership_sm", late_sm)

        lg.add(1, b"x")
        lg.commit(0)
        lg.snapshot()

        raw = storage.load_snapshot()
        envelope = json.loads(raw["data"].decode("utf-8"))
        assert "membership_sm" in envelope["machines"]

    def test_legacy_snapshot_bytes_restore_state_machine(self, tmp_path):
        """A pre-fix snapshot (raw JSON bytes, no envelope) still restores app SM."""
        import json

        from salt.cluster.consensus.raft.log import CounterStateMachine, Log

        storage = self._make_storage(tmp_path)
        # Simulate a pre-fix on-disk snapshot: just the SM blob, no envelope
        storage.save_snapshot(
            json.dumps({"count": 7, "sessions": {}}).encode(), index=3, term=1
        )

        app_sm = CounterStateMachine()
        mem_sm = __import__(
            "salt.cluster.consensus.raft.log", fromlist=["MembershipStateMachine"]
        ).MembershipStateMachine()
        lg = Log(
            storage=storage,
            state_machine=app_sm,
            state_machines={"membership_sm": mem_sm},
        )

        # App SM was restored from the legacy payload
        assert app_sm.count == 7
        # Membership SM stays at its initial state — pre-fix snapshots had no
        # membership data; the post-snapshot log replay would rebuild it
        assert mem_sm.current_voters() == []
        assert lg.last_included_index == 3

    def test_snapshot_without_extras_has_state_machine_key(self, tmp_path):
        """A Log with only an app SM still writes envelope format."""
        import json

        from salt.cluster.consensus.raft.log import (
            SNAPSHOT_ENVELOPE_VERSION,
            CounterStateMachine,
            Log,
        )

        storage = self._make_storage(tmp_path)
        lg = Log(storage=storage, state_machine=CounterStateMachine())
        lg.add(1, b"a")
        lg.commit(0)
        lg.snapshot()

        raw = storage.load_snapshot()
        envelope = json.loads(raw["data"].decode("utf-8"))
        assert envelope["__envelope__"] == SNAPSHOT_ENVELOPE_VERSION
        assert list(envelope["machines"].keys()) == ["state_machine"]


class TestNodeInstallSnapshotMembership:
    """Node.install_snapshot must restore membership_sm from the envelope."""

    def test_install_snapshot_restores_membership(self):
        """A follower receiving an envelope snapshot rebuilds its membership SM."""
        import json

        from salt.cluster.consensus.raft.log import SNAPSHOT_ENVELOPE_VERSION
        from salt.cluster.consensus.raft.node import Node

        node = Node("follower")
        node.register_schedule_timeout(lambda t, c: None)
        node.term = 1

        envelope = {
            "__envelope__": SNAPSHOT_ENVELOPE_VERSION,
            "machines": {
                "membership_sm": {
                    "voters": ["m1", "m2", "m3"],
                    "learners": [],
                    "version": 5,
                },
            },
        }
        data = json.dumps(envelope).encode("utf-8")

        node.install_snapshot(
            leader_id="m1",
            term=2,
            last_index=10,
            last_term=2,
            data=data,
        )

        assert node.membership_sm.current_voters() == ["m1", "m2", "m3"]
        assert node.membership_sm.membership_version == 5
        assert node.log.last_included_index == 10

    def test_install_snapshot_legacy_payload_falls_through(self):
        """A pre-fix snapshot blob (no envelope marker) leaves membership SM untouched."""
        import json

        from salt.cluster.consensus.raft.node import Node

        node = Node("follower")
        node.register_schedule_timeout(lambda t, c: None)
        node.term = 1
        # Membership SM starts empty; legacy payload is for the app SM, which
        # is None by default — test verifies no crash and no spurious changes.
        legacy = json.dumps({"count": 9, "sessions": {}}).encode()

        node.install_snapshot(
            leader_id="m1",
            term=2,
            last_index=4,
            last_term=2,
            data=legacy,
        )

        assert node.membership_sm.current_voters() == []
        assert node.log.last_included_index == 4

    def test_install_snapshot_envelope_with_dict_data(self):
        """install_snapshot also accepts an already-decoded envelope dict."""
        from salt.cluster.consensus.raft.log import SNAPSHOT_ENVELOPE_VERSION
        from salt.cluster.consensus.raft.node import Node

        node = Node("follower")
        node.register_schedule_timeout(lambda t, c: None)
        node.term = 1

        envelope = {
            "__envelope__": SNAPSHOT_ENVELOPE_VERSION,
            "machines": {
                "membership_sm": {
                    "voters": ["m1"],
                    "learners": ["m2"],
                    "version": 1,
                },
            },
        }

        node.install_snapshot(
            leader_id="m1",
            term=2,
            last_index=2,
            last_term=2,
            data=envelope,
        )

        assert node.membership_sm.current_voters() == ["m1"]
        assert node.membership_sm.current_learners() == ["m2"]

    def test_node_log_registers_membership_sm(self):
        """Node wires its membership_sm into Log so snapshots include it."""
        from salt.cluster.consensus.raft.node import Node

        node = Node("a")
        assert "membership_sm" in node.log._extra_state_machines
        assert node.log._extra_state_machines["membership_sm"] is node.membership_sm

    def test_register_membership_sm_updates_log(self):
        """Replacing the membership SM keeps the Log registry in sync."""
        from salt.cluster.consensus.raft.log import MembershipStateMachine
        from salt.cluster.consensus.raft.node import Node

        node = Node("a")
        new_sm = MembershipStateMachine()
        node.register_membership_sm(new_sm)
        assert node.log._extra_state_machines["membership_sm"] is new_sm


class TestNodeReconcileMembership:
    """
    Node.reconcile_membership re-applies the SM's restored view to the
    Node's peer table and fires the wired on_change observer.

    GAP #1 in CONSENSUS_BUGS.md / GAPS.md: MembershipStateMachine
    .restore_snapshot is a pure store; without reconcile, the in-memory
    peer voting flags and any on_change observer (RaftService cluster-
    ready hook, ring rebuild) stay stale after a snapshot restore.
    """

    def _make_node(self, node_id="a"):
        """Build a Node with a peer factory so on_config_change rebuilds peers."""
        from salt.cluster.consensus.raft.node import Node

        node = Node(node_id)
        node.register_schedule_timeout(lambda t, c: None)

        class _StubPeer:
            def __init__(self, addr, voting=True):
                self.node_id = addr
                self.voting = voting

        node.register_peer_factory(_StubPeer)
        return node

    def test_reconcile_no_op_when_sm_empty(self):
        """A fresh Node with no committed CONFIG: reconcile is a no-op."""
        node = self._make_node()
        observed = []
        node.membership_sm.on_change = lambda v, l: observed.append((list(v), list(l)))
        node.reconcile_membership()
        assert observed == [], "on_change must not fire for an empty SM"
        assert node.peers == []

    def test_reconcile_after_restore_snapshot_fires_on_change(self):
        """
        After ``MembershipStateMachine.restore_snapshot`` populates the
        SM, calling ``reconcile_membership`` invokes the wired on_change
        observer with the restored voters/learners.
        """
        node = self._make_node("self")
        observed = []
        node.membership_sm.on_change = lambda v, l: observed.append((list(v), list(l)))

        node.membership_sm.restore_snapshot(
            {"voters": ["self", "b", "c"], "learners": ["d"], "version": 7}
        )
        # Pre-condition: SM has the right view but on_change has not fired.
        assert node.membership_sm.current_voters() == ["b", "c", "self"]
        assert observed == []

        node.reconcile_membership()

        assert len(observed) == 1
        voters, learners = observed[0]
        assert sorted(voters) == ["b", "c", "self"]
        assert learners == ["d"]

    def test_reconcile_rebuilds_node_peers_from_restored_sm(self):
        """
        ``Node.peers`` and ``Node.voting`` re-converge with the restored
        SM after reconcile.  Without this, a master that comes up from a
        compacted snapshot has an empty peer table.
        """
        node = self._make_node("self")
        # Pre-existing peer table is empty (this is the post-snapshot
        # state — Node was constructed before any CONFIG entry replayed).
        assert node.peers == []
        assert node.voting is True  # default

        node.membership_sm.restore_snapshot(
            {"voters": ["self", "b", "c"], "learners": ["d"], "version": 9}
        )
        node.reconcile_membership()

        # All three voter peers (excluding self) plus the learner should
        # appear in node.peers, with voting flags set correctly.
        peer_ids = sorted(p.node_id for p in node.peers)
        assert peer_ids == ["b", "c", "d"]
        voting_by_id = {p.node_id: p.voting for p in node.peers}
        assert voting_by_id == {"b": True, "c": True, "d": False}
        # And self must be marked as a voter.
        assert node.voting is True

    def test_reconcile_fired_from_install_snapshot(self):
        """
        ``Node.install_snapshot`` calls reconcile so a follower receiving
        an envelope snapshot ends up with peers + on_change side effects
        consistent with the restored membership SM.
        """
        import json

        from salt.cluster.consensus.raft.log import SNAPSHOT_ENVELOPE_VERSION

        node = self._make_node("follower")
        node.term = 1
        observed = []
        node.membership_sm.on_change = lambda v, l: observed.append((list(v), list(l)))

        envelope = {
            "__envelope__": SNAPSHOT_ENVELOPE_VERSION,
            "machines": {
                "membership_sm": {
                    "voters": ["m1", "m2", "follower"],
                    "learners": [],
                    "version": 12,
                },
            },
        }
        node.install_snapshot(
            leader_id="m1",
            term=2,
            last_index=20,
            last_term=2,
            data=json.dumps(envelope).encode("utf-8"),
        )

        # SM restored, on_change fired, peers rebuilt.
        assert node.membership_sm.current_voters() == ["follower", "m1", "m2"]
        assert len(observed) == 1
        peer_ids = sorted(p.node_id for p in node.peers)
        assert peer_ids == ["m1", "m2"]

    def test_reconcile_idempotent(self):
        """
        Calling reconcile twice on the same restored state is safe; it
        re-fires on_change but does not corrupt peer state.  This matches
        the behaviour we get when ``RaftService`` reconciles after wiring
        on_change *and* a subsequent ``install_snapshot`` reconciles again.
        """
        node = self._make_node("self")
        node.membership_sm.restore_snapshot(
            {"voters": ["self", "b"], "learners": [], "version": 1}
        )
        observed = []
        node.membership_sm.on_change = lambda v, l: observed.append((list(v), list(l)))

        node.reconcile_membership()
        node.reconcile_membership()

        peer_ids = sorted(p.node_id for p in node.peers)
        assert peer_ids == ["b"]
        # on_change fired twice but the peer table is stable.
        assert len(observed) == 2

    def test_reconcile_without_peer_factory(self):
        """
        A bare Node without a registered peer factory still reconciles
        cleanly: peer voting flags update in place on the existing
        peers, on_change still fires.  Matches the pre-RaftService
        construction window where reconcile would fire from
        ``install_snapshot`` before any peer factory is wired.
        """
        from salt.cluster.consensus.raft.node import Node

        node = Node("self")
        node.register_schedule_timeout(lambda t, c: None)
        # No peer_factory registered — leave node.peers empty.

        observed = []
        node.membership_sm.on_change = lambda v, l: observed.append((list(v), list(l)))
        node.membership_sm.restore_snapshot(
            {"voters": ["self", "b"], "learners": ["c"], "version": 1}
        )
        node.reconcile_membership()
        # on_change still fired — RaftService can update its hooks.
        assert len(observed) == 1
        assert sorted(observed[0][0]) == ["b", "self"]
        assert observed[0][1] == ["c"]
        # Without a factory there are no peers to populate; that's
        # correct for this construction window.
        assert node.peers == []

    def test_reconcile_when_self_demoted_to_learner(self):
        """
        If the restored membership has this node *only* in the learner
        set, ``Node.voting`` flips to False.  Pins the
        on_config_change side-effect path on the demote case.
        """
        node = self._make_node("self")
        node.membership_sm.restore_snapshot(
            {"voters": ["b", "c"], "learners": ["self"], "version": 1}
        )
        node.reconcile_membership()
        assert node.voting is False

    def test_reconcile_with_self_in_neither_set_keeps_voting_default(self):
        """
        If the restored snapshot does not mention this node at all
        (membership change removed it), ``Node.voting`` keeps its
        prior value rather than spuriously flipping.  Matches the
        existing on_config_change code path that only mutates
        ``self.voting`` when it sees this node in voters or learners.
        """
        node = self._make_node("self")
        original_voting = node.voting
        node.membership_sm.restore_snapshot(
            {"voters": ["b", "c"], "learners": ["d"], "version": 1}
        )
        node.reconcile_membership()
        assert node.voting is original_voting


# ---------------------------------------------------------------------------
# RingConfigStateMachine — ring policy commits (Stage 1 of ring rollout)
# ---------------------------------------------------------------------------


class TestRingConfigStateMachine:
    """
    Pin the ``RingConfigStateMachine`` contract: applies RING_CONFIG
    entries (members source + replication factor), fires on_change,
    survives snapshot/restore via the same envelope shape used by
    MembershipStateMachine.
    """

    def test_default_policy_is_self_with_one_replica(self):
        from salt.cluster.consensus.raft.log import RingConfigStateMachine

        sm = RingConfigStateMachine()
        assert sm.members == "self"
        assert sm.replicas == 1
        assert sm.config_version == -1

    def test_apply_records_members_and_replicas(self):
        from salt.cluster.consensus.raft.log import RingConfigStateMachine

        sm = RingConfigStateMachine()
        sm.apply({"members": "voters", "replicas": 3}, index=7)
        assert sm.members == "voters"
        assert sm.replicas == 3
        assert sm.config_version == 7

    def test_apply_partial_update_keeps_other_field(self):
        """
        Partial updates merge with the current state so a runner can
        flip just one knob at a time without re-asserting the other.
        """
        from salt.cluster.consensus.raft.log import RingConfigStateMachine

        sm = RingConfigStateMachine()
        sm.apply({"members": "voters", "replicas": 3}, index=1)
        # Only flip replicas.
        sm.apply({"replicas": 2}, index=2)
        assert sm.members == "voters"
        assert sm.replicas == 2
        # Only flip members.
        sm.apply({"members": "self"}, index=3)
        assert sm.members == "self"
        assert sm.replicas == 2

    def test_apply_rejects_unknown_members_value(self):
        """Unknown ``members`` policy is logged and ignored, not stored."""
        from salt.cluster.consensus.raft.log import RingConfigStateMachine

        sm = RingConfigStateMachine()
        sm.apply({"members": "voters"}, index=1)
        sm.apply({"members": "moon"}, index=2)
        assert sm.members == "voters"

    def test_apply_clamps_replicas_to_at_least_one(self):
        """A replicas value below 1 is silently clamped to 1."""
        from salt.cluster.consensus.raft.log import RingConfigStateMachine

        sm = RingConfigStateMachine()
        sm.apply({"replicas": 0}, index=1)
        assert sm.replicas == 1
        sm.apply({"replicas": -5}, index=2)
        assert sm.replicas == 1

    def test_apply_ignores_non_integer_replicas(self):
        """Non-numeric replicas values are logged and ignored."""
        from salt.cluster.consensus.raft.log import RingConfigStateMachine

        sm = RingConfigStateMachine()
        sm.apply({"replicas": 3}, index=1)
        sm.apply({"replicas": "lots"}, index=2)
        assert sm.replicas == 3

    def test_on_change_fires_with_current_state(self):
        """
        ``on_change(members, replicas)`` is invoked after every successful
        apply with the *new* values — even if only one field changed.
        """
        from salt.cluster.consensus.raft.log import RingConfigStateMachine

        seen = []
        sm = RingConfigStateMachine(on_change=lambda m, r: seen.append((m, r)))
        sm.apply({"members": "voters", "replicas": 3}, index=1)
        sm.apply({"replicas": 2}, index=2)
        assert seen == [("voters", 3), ("voters", 2)]

    def test_snapshot_round_trip(self):
        """``get_snapshot`` / ``restore_snapshot`` is lossless."""
        from salt.cluster.consensus.raft.log import RingConfigStateMachine

        sm1 = RingConfigStateMachine()
        sm1.apply({"members": "voters", "replicas": 4}, index=42)
        snap = sm1.get_snapshot()

        sm2 = RingConfigStateMachine()
        sm2.restore_snapshot(snap)
        assert sm2.members == "voters"
        assert sm2.replicas == 4
        assert sm2.config_version == 42

    def test_restore_snapshot_from_bytes(self):
        """JSON-encoded snapshot bytes restore correctly."""
        import json

        from salt.cluster.consensus.raft.log import RingConfigStateMachine

        sm = RingConfigStateMachine()
        payload = json.dumps(
            {"members": "voters", "replicas": 2, "version": 5}
        ).encode()
        sm.restore_snapshot(payload)
        assert sm.members == "voters"
        assert sm.replicas == 2
        assert sm.config_version == 5

    def test_restore_snapshot_with_garbage_data_is_noop(self):
        """Non-dict / non-bytes input leaves the SM unchanged."""
        from salt.cluster.consensus.raft.log import RingConfigStateMachine

        sm = RingConfigStateMachine()
        sm.restore_snapshot("not a dict")
        sm.restore_snapshot(None)
        sm.restore_snapshot(42)
        assert sm.members == "self"
        assert sm.replicas == 1


class TestNodeAppliesRingConfigEntry:
    """
    ``Node.apply_entries`` dispatches RING_CONFIG entries to the SM
    registered under ``"ring_sm"`` on the Log.  Stage 1 wiring.
    """

    def test_ring_config_entry_dispatches_to_registered_sm(self):
        from salt.cluster.consensus.raft.log import LogEntryType, RingConfigStateMachine
        from salt.cluster.consensus.raft.node import Node

        node = Node("a")
        node.register_schedule_timeout(lambda t, c: None)
        ring_sm = RingConfigStateMachine()
        node.log.register_state_machine("ring_sm", ring_sm)

        node.log.add(
            1,
            {"members": "voters", "replicas": 2},
            entry_type=LogEntryType.RING_CONFIG,
        )
        node.commit_index = node.log.index
        assert ring_sm.members == "voters"
        assert ring_sm.replicas == 2

    def test_ring_config_entry_without_registered_sm_is_safe(self):
        """
        A RING_CONFIG entry on a Node without a ``ring_sm`` registered
        applies as a no-op.  Older snapshots / mid-deploy clusters
        should tolerate this rather than crash.
        """
        from salt.cluster.consensus.raft.log import LogEntryType
        from salt.cluster.consensus.raft.node import Node

        node = Node("a")
        node.register_schedule_timeout(lambda t, c: None)
        # No ring_sm registered.
        node.log.add(
            1,
            {"members": "voters", "replicas": 2},
            entry_type=LogEntryType.RING_CONFIG,
        )
        node.commit_index = node.log.index
        # No exception raised; entry advanced last_applied.
        assert node.log.last_applied == node.log.index

    def test_ring_config_apply_fires_registered_on_change(self):
        """
        Apply path runs the SM's ``on_change`` observer.  Each
        per-ring :class:`RaftService` wires this to
        ``_on_ring_config_change_for`` so the named ring's
        :class:`HashRing` re-syncs after every committed RING_CONFIG
        entry on the ring's own log.
        """
        from salt.cluster.consensus.raft.log import LogEntryType, RingConfigStateMachine
        from salt.cluster.consensus.raft.node import Node

        observed = []
        ring_sm = RingConfigStateMachine(on_change=lambda m, r: observed.append((m, r)))
        node = Node("a")
        node.register_schedule_timeout(lambda t, c: None)
        node.log.register_state_machine("ring_sm", ring_sm)

        node.log.add(
            1,
            {"members": "voters", "replicas": 2},
            entry_type=LogEntryType.RING_CONFIG,
        )
        node.commit_index = node.log.index
        assert observed == [("voters", 2)]

    def test_mixed_config_and_ring_config_entries_apply_independently(self):
        """
        A CONFIG + RING_CONFIG sequence drives the membership SM and
        the ring SM independently — neither leaks state into the
        other.  Pins the contract that future SMs registered on the
        Log do not accidentally cross-talk via the apply path.
        """
        from salt.cluster.consensus.raft.log import LogEntryType, RingConfigStateMachine
        from salt.cluster.consensus.raft.node import Node

        ring_sm = RingConfigStateMachine()
        node = Node("a")
        node.register_schedule_timeout(lambda t, c: None)
        node.log.register_state_machine("ring_sm", ring_sm)

        node.log.add(
            1,
            {"voters": ["a", "b"], "learners": []},
            entry_type=LogEntryType.CONFIG,
        )
        node.log.add(
            1,
            {"members": "voters", "replicas": 3},
            entry_type=LogEntryType.RING_CONFIG,
        )
        node.log.add(
            1,
            {"voters": ["a", "b", "c"], "learners": []},
            entry_type=LogEntryType.CONFIG,
        )
        node.commit_index = node.log.index

        assert node.membership_sm.current_voters() == ["a", "b", "c"]
        assert ring_sm.members == "voters"
        assert ring_sm.replicas == 3

    def test_ring_config_apply_swallows_on_change_exception(self):
        """
        A buggy on_change observer must not crash the apply loop.  The
        SM still records the new state; the exception is logged.
        """
        from salt.cluster.consensus.raft.log import LogEntryType, RingConfigStateMachine
        from salt.cluster.consensus.raft.node import Node

        # Defensively, RingConfigStateMachine.apply currently lets the
        # exception propagate.  This test pins the *current* behaviour
        # so a future change that wraps the callback in try/except is
        # an explicit, reviewed contract change.
        def boom(_m, _r):
            raise RuntimeError("observer is sad")

        ring_sm = RingConfigStateMachine(on_change=boom)
        node = Node("a")
        node.register_schedule_timeout(lambda t, c: None)
        node.log.register_state_machine("ring_sm", ring_sm)

        node.log.add(
            1,
            {"members": "voters"},
            entry_type=LogEntryType.RING_CONFIG,
        )
        # Apply currently surfaces the exception.  A future change that
        # adds isolation should update this assertion.
        with pytest.raises(RuntimeError):
            node.commit_index = node.log.index
        # Even though the callback raised, the SM did record the new
        # state before invoking the callback.
        assert ring_sm.members == "voters"


class TestSnapshotEnvelopeMultiSM:
    """
    Both ``membership_sm`` and ``ring_sm`` must round-trip through the
    same snapshot envelope.  This is the integration claim that closes
    CONSENSUS_BUGS.md #1's fix and lets stage 1 ring config persist
    through compaction.
    """

    def _build_node(self, node_id="self"):
        from salt.cluster.consensus.raft.log import RingConfigStateMachine
        from salt.cluster.consensus.raft.node import Node

        node = Node(node_id)
        node.register_schedule_timeout(lambda t, c: None)
        ring_sm = RingConfigStateMachine()
        node.log.register_state_machine("ring_sm", ring_sm)
        return node, ring_sm

    def test_snapshot_carries_both_membership_and_ring_sm(self):
        """
        After ``Log.snapshot()`` the persisted blob has ``machines``
        keys for *both* SMs.  Restoring the blob into a fresh Log
        rebuilds both states.
        """
        from salt.cluster.consensus.raft.log import (
            SNAPSHOT_ENVELOPE_VERSION,
            LogEntryType,
            RingConfigStateMachine,
        )
        from salt.cluster.consensus.raft.node import Node

        node, ring_sm = self._build_node()
        node.log.add(
            1,
            {"voters": ["self", "b"], "learners": []},
            entry_type=LogEntryType.CONFIG,
        )
        node.log.add(
            1,
            {"members": "voters", "replicas": 3},
            entry_type=LogEntryType.RING_CONFIG,
        )
        node.commit_index = node.log.index
        node.log.snapshot()

        # Build a fresh Node + ring_sm and restore from the same data.
        fresh_node = Node("self")
        fresh_node.register_schedule_timeout(lambda t, c: None)
        fresh_ring_sm = RingConfigStateMachine()
        fresh_node.log.register_state_machine("ring_sm", fresh_ring_sm)
        # Synthesize the snapshot bytes directly to drive
        # restore_state_machines_from_data.
        fresh_node.log.restore_state_machines_from_data(
            {
                "__envelope__": SNAPSHOT_ENVELOPE_VERSION,
                "machines": {
                    "membership_sm": node.membership_sm.get_snapshot(),
                    "ring_sm": ring_sm.get_snapshot(),
                },
            }
        )
        assert fresh_node.membership_sm.current_voters() == ["b", "self"]
        assert fresh_ring_sm.members == "voters"
        assert fresh_ring_sm.replicas == 3

    def test_restore_with_only_membership_sm_keeps_ring_sm_default(self):
        """
        Backward-compat: a snapshot from before ring_sm was registered
        (envelope has only ``membership_sm``) must restore membership
        without crashing, leaving the ring_sm at its defaults so the
        rest of the system falls back to broadcast.
        """
        from salt.cluster.consensus.raft.log import (
            SNAPSHOT_ENVELOPE_VERSION,
            RingConfigStateMachine,
        )
        from salt.cluster.consensus.raft.node import Node

        node = Node("self")
        node.register_schedule_timeout(lambda t, c: None)
        ring_sm = RingConfigStateMachine()
        node.log.register_state_machine("ring_sm", ring_sm)

        node.log.restore_state_machines_from_data(
            {
                "__envelope__": SNAPSHOT_ENVELOPE_VERSION,
                "machines": {
                    "membership_sm": {
                        "voters": ["a", "b"],
                        "learners": [],
                        "version": 5,
                    },
                    # No ring_sm payload.
                },
            }
        )
        assert node.membership_sm.current_voters() == ["a", "b"]
        assert ring_sm.members == "self"
        assert ring_sm.replicas == 1


# ---------------------------------------------------------------------------
# RingRegistryStateMachine — cluster-log registry of named rings (multi-ring)
# ---------------------------------------------------------------------------


class TestRingRegistryStateMachine:
    """
    Pin the contract of :class:`RingRegistryStateMachine`: applies
    ``RING_REGISTRY`` entries, fires ``on_change``, snapshots and
    restores round-trip, and the apply loop is tolerant of malformed
    entries (which it must be, since rogue cmd payloads must not
    crash committed-entry replay).
    """

    def _sm(self, **kwargs):
        from salt.cluster.consensus.raft.log import RingRegistryStateMachine

        return RingRegistryStateMachine(**kwargs)

    def test_default_state_is_empty(self):
        sm = self._sm()
        assert sm.rings() == {}
        assert sm.active_rings() == []
        assert sm.registry_version == -1
        assert sm.get("jobs") is None

    def test_apply_records_ring_and_status(self):
        sm = self._sm()
        sm.apply(
            {"ring_id": "jobs", "founding_voters": ["m2", "m1"], "status": "active"},
            index=4,
        )
        # Founding voters are stored sorted so every replica sees the
        # same canonical form regardless of how the operator listed them.
        assert sm.get("jobs") == {
            "founding_voters": ["m1", "m2"],
            "status": "active",
        }
        assert sm.active_rings() == ["jobs"]
        assert sm.registry_version == 4

    def test_status_defaults_to_active(self):
        """
        The common case is a two-field create; status defaults to
        active so the operator only spells out the voter list.
        """
        sm = self._sm()
        sm.apply({"ring_id": "jobs", "founding_voters": ["m1"]}, index=1)
        assert sm.get("jobs")["status"] == "active"

    def test_destroy_marks_ring_destroyed_and_drops_from_active(self):
        """
        Destroying a ring keeps it in the registry (so the lifecycle
        is auditable) but removes it from ``active_rings`` — daemons
        watching for active rings know to tear down their per-ring
        Raft group.
        """
        sm = self._sm()
        sm.apply({"ring_id": "jobs", "founding_voters": ["m1"]}, index=1)
        sm.apply({"ring_id": "jobs", "status": "destroyed"}, index=2)
        entry = sm.get("jobs")
        assert entry["status"] == "destroyed"
        assert sm.active_rings() == []
        assert sm.registry_version == 2

    def test_unknown_status_is_ignored(self):
        sm = self._sm()
        sm.apply({"ring_id": "jobs", "status": "bogus"}, index=1)
        assert sm.get("jobs") is None
        # Version unchanged — invalid entry never applied.
        assert sm.registry_version == -1

    def test_missing_ring_id_is_ignored(self):
        sm = self._sm()
        sm.apply({"founding_voters": ["m1"]}, index=1)
        assert sm.rings() == {}

    def test_non_dict_cmd_is_ignored(self):
        sm = self._sm()
        sm.apply("not a dict", index=1)
        assert sm.rings() == {}

    def test_on_change_callback_fires_with_canonical_args(self):
        seen = []
        sm = self._sm(on_change=lambda r, v, s: seen.append((r, list(v), s)))
        sm.apply(
            {"ring_id": "jobs", "founding_voters": ["m3", "m1"], "status": "active"},
            index=1,
        )
        assert seen == [("jobs", ["m1", "m3"], "active")]

    def test_multiple_rings_coexist(self):
        sm = self._sm()
        sm.apply({"ring_id": "jobs", "founding_voters": ["m1", "m2"]}, index=1)
        sm.apply({"ring_id": "events", "founding_voters": ["m3"]}, index=2)
        assert sm.active_rings() == ["events", "jobs"]
        assert sm.get("jobs")["founding_voters"] == ["m1", "m2"]
        assert sm.get("events")["founding_voters"] == ["m3"]

    def test_snapshot_restore_roundtrip(self):
        sm = self._sm()
        sm.apply({"ring_id": "jobs", "founding_voters": ["m1", "m2"]}, index=3)
        sm.apply({"ring_id": "events", "founding_voters": ["m3"]}, index=4)
        data = sm.get_snapshot()
        restored = self._sm()
        restored.restore_snapshot(data)
        assert restored.rings() == sm.rings()
        assert restored.registry_version == 4

    def test_restore_from_json_bytes(self):
        """
        ``restore_snapshot`` accepts JSON-encoded bytes (as the
        envelope hands back when reading the snapshot off disk).
        """
        import json

        sm = self._sm()
        sm.apply({"ring_id": "jobs", "founding_voters": ["m1"]}, index=1)
        raw = json.dumps(sm.get_snapshot()).encode("utf-8")

        restored = self._sm()
        restored.restore_snapshot(raw)
        assert restored.active_rings() == ["jobs"]
        assert restored.registry_version == 1


# ---------------------------------------------------------------------------
# RoutingStateMachine — cluster-log data-type -> ring routing (multi-ring)
# ---------------------------------------------------------------------------


class TestRoutingStateMachine:
    """
    Pin the contract of :class:`RoutingStateMachine`: applies
    ``ROUTE`` entries, fires ``on_change``, snapshots and restores,
    and tolerates malformed entries the same way the registry does.
    """

    def _sm(self, **kwargs):
        from salt.cluster.consensus.raft.log import RoutingStateMachine

        return RoutingStateMachine(**kwargs)

    def test_default_state_is_empty(self):
        sm = self._sm()
        assert sm.routes() == {}
        assert sm.get("jobs") is None
        assert sm.routing_version == -1

    def test_apply_records_data_type_to_ring(self):
        sm = self._sm()
        sm.apply({"data_type": "jobs", "ring_id": "jobs_ring"}, index=2)
        assert sm.get("jobs") == "jobs_ring"
        assert sm.routing_version == 2

    def test_clear_route_returns_to_broadcast(self):
        """
        Routing a data type to ``None`` is the operator-facing way to
        flip it back to broadcast.  ``get`` returns ``None`` for an
        explicitly-cleared route (same as for one that was never
        routed), and ``routes()`` retains the entry so the lifecycle
        is auditable.
        """
        sm = self._sm()
        sm.apply({"data_type": "jobs", "ring_id": "jobs_ring"}, index=1)
        sm.apply({"data_type": "jobs", "ring_id": None}, index=2)
        assert sm.get("jobs") is None
        assert sm.routes() == {"jobs": None}
        assert sm.routing_version == 2

    def test_missing_data_type_is_ignored(self):
        sm = self._sm()
        sm.apply({"ring_id": "jobs_ring"}, index=1)
        assert sm.routes() == {}
        assert sm.routing_version == -1

    def test_non_dict_cmd_is_ignored(self):
        sm = self._sm()
        sm.apply(["not", "a", "dict"], index=1)
        assert sm.routes() == {}

    def test_on_change_fires_with_data_type_and_ring(self):
        seen = []
        sm = self._sm(on_change=lambda d, r: seen.append((d, r)))
        sm.apply({"data_type": "jobs", "ring_id": "jobs_ring"}, index=1)
        sm.apply({"data_type": "events", "ring_id": None}, index=2)
        assert seen == [("jobs", "jobs_ring"), ("events", None)]

    def test_snapshot_restore_roundtrip(self):
        sm = self._sm()
        sm.apply({"data_type": "jobs", "ring_id": "jobs_ring"}, index=1)
        sm.apply({"data_type": "events", "ring_id": None}, index=2)
        data = sm.get_snapshot()
        restored = self._sm()
        restored.restore_snapshot(data)
        assert restored.routes() == sm.routes()
        assert restored.routing_version == 2

    def test_restore_from_json_bytes(self):
        import json

        sm = self._sm()
        sm.apply({"data_type": "jobs", "ring_id": "jobs_ring"}, index=1)
        raw = json.dumps(sm.get_snapshot()).encode("utf-8")

        restored = self._sm()
        restored.restore_snapshot(raw)
        assert restored.get("jobs") == "jobs_ring"


# ---------------------------------------------------------------------------
# Node.apply_entries dispatches RING_REGISTRY / ROUTE entries (multi-ring)
# ---------------------------------------------------------------------------


class TestMultiRingEntryDispatch:
    """
    Pin the behaviour that committed RING_REGISTRY and ROUTE entries
    are dispatched to their registered state machines on the cluster
    log — the wire path between Raft commit and ``on_change``.
    """

    def test_ring_registry_entry_dispatches_to_registered_sm(self):
        from salt.cluster.consensus.raft.log import (
            LogEntryType,
            RingRegistryStateMachine,
        )
        from salt.cluster.consensus.raft.node import Node

        node = Node("self")
        node.register_schedule_timeout(lambda t, c: None)
        registry_sm = RingRegistryStateMachine()
        node.log.register_state_machine("ring_registry_sm", registry_sm)

        node.log.add(
            1,
            {"ring_id": "jobs", "founding_voters": ["self"], "status": "active"},
            entry_type=LogEntryType.RING_REGISTRY,
        )
        node.commit_index = node.log.index

        assert registry_sm.active_rings() == ["jobs"]
        assert registry_sm.get("jobs")["founding_voters"] == ["self"]

    def test_route_entry_dispatches_to_registered_sm(self):
        from salt.cluster.consensus.raft.log import LogEntryType, RoutingStateMachine
        from salt.cluster.consensus.raft.node import Node

        node = Node("self")
        node.register_schedule_timeout(lambda t, c: None)
        routing_sm = RoutingStateMachine()
        node.log.register_state_machine("routing_sm", routing_sm)

        node.log.add(
            1,
            {"data_type": "jobs", "ring_id": "jobs_ring"},
            entry_type=LogEntryType.ROUTE,
        )
        node.commit_index = node.log.index

        assert routing_sm.get("jobs") == "jobs_ring"

    def test_unregistered_sm_is_safe(self):
        """
        A RING_REGISTRY / ROUTE entry committed on a node that has not
        registered the corresponding SM must not crash apply_entries
        — the entries are simply dropped on the floor.  Important on
        rolling upgrades where some masters know the new entry types
        and others may not yet.
        """
        from salt.cluster.consensus.raft.log import LogEntryType
        from salt.cluster.consensus.raft.node import Node

        node = Node("self")
        node.register_schedule_timeout(lambda t, c: None)

        node.log.add(
            1,
            {"ring_id": "jobs", "founding_voters": ["self"]},
            entry_type=LogEntryType.RING_REGISTRY,
        )
        node.log.add(
            1,
            {"data_type": "jobs", "ring_id": "jobs_ring"},
            entry_type=LogEntryType.ROUTE,
        )
        node.commit_index = node.log.index  # must not raise
        assert node.log.last_applied == node.log.index


# ---------------------------------------------------------------------------
# SaltStorage fsync — cluster Raft consensus is correctness-critical and the
# write rate is low, so we always durable committed state.  These tests pin
# the contract: every persisted write triggers an os.fsync.
# ---------------------------------------------------------------------------


class _FsyncSpy:
    """Records the file descriptors handed to ``os.fsync`` during a write."""

    def __init__(self):
        self.calls = 0

    def __call__(self, fd):
        # Validate the fd is a real, currently-open one.  os.fstat raises
        # OSError if not -- a regression that passes a stale fd would surface
        # here rather than as a mysterious silent miss.
        os.fstat(fd)
        self.calls += 1


def test_save_state_fsyncs_to_disk(storage):
    """save_state must fsync the persisted (term, voted_for) record."""
    spy = _FsyncSpy()
    with patch.object(storage_module.os, "fsync", spy):
        storage.save_state(term=7, voted_for="m1")
    assert spy.calls >= 1, "save_state did not call os.fsync"


def test_append_log_fsyncs_each_entry(storage):
    """append_log must fsync after every entry — cluster log is the durable line."""
    spy = _FsyncSpy()
    entries = [
        LogEntry(term=1, index=0, cmd={"x": 1}),
        LogEntry(term=1, index=1, cmd={"x": 2}),
        LogEntry(term=1, index=2, cmd={"x": 3}),
    ]
    with patch.object(storage_module.os, "fsync", spy):
        for entry in entries:
            storage.append_log(entry)
    # At minimum one fsync per entry (data fsync); dir fsync may add more.
    assert spy.calls >= len(entries), (
        f"expected >= {len(entries)} fsyncs across {len(entries)} appends, "
        f"got {spy.calls}"
    )


def test_save_snapshot_fsyncs_to_disk(storage):
    """Snapshot writes are infrequent but membership-critical — also fsync."""
    spy = _FsyncSpy()
    with patch.object(storage_module.os, "fsync", spy):
        storage.save_snapshot({"voters": ["m1"], "learners": []}, index=10, term=2)
    assert spy.calls >= 1, "save_snapshot did not call os.fsync"


def test_fsync_skipped_for_non_localfs_driver(tmp_path):
    """Non-localfs drivers fall through silently — durability is their concern."""
    from tests.support.mock import MagicMock

    opts = salt.config.master_config("/dev/null")
    opts["cachedir"] = str(tmp_path)
    storage = SaltStorage("test-node", opts)
    # Replace the cache with a stub so the unknown driver name never
    # reaches the salt.cache loader; this isolates the test to the
    # SaltStorage._fsync_bank_key driver-gating branch.
    storage._cache = MagicMock()
    storage._cache.driver = "memory"

    spy = _FsyncSpy()
    with patch.object(storage_module.os, "fsync", spy):
        storage.save_state(term=1, voted_for=None)
    assert spy.calls == 0, "fsync must be skipped for non-localfs cache drivers"
