"""Tests for ``salt.cluster.consensus.raft`` log and storage."""

import pytest

import salt.config
from salt.cluster.consensus.raft import (
    CounterStateMachine,
    Log,
    LogEntry,
    LogEntryCommitStatus,
    LogEntryType,
)
from salt.cluster.consensus.storage import SaltStorage


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
    assert storage.load_state() == {"term": 7, "voted_for": "voter-a"}
    storage.save_state(8, None)
    assert storage.load_state() == {"term": 8, "voted_for": None}


def test_salt_storage_log_append_and_reload(storage):
    e0 = LogEntry(1, 0, "a", None, LogEntryType.COMMAND)
    storage.append_log(e0)
    storage.append_log(LogEntry(1, 1, "b", None, LogEntryType.COMMAND))
    loaded = storage.load_log()
    assert len(loaded) == 2
    assert loaded[0].cmd == "a"
    assert loaded[1].index == 1


def test_salt_storage_defaults_when_empty(storage):
    assert storage.load_state() == {"term": 0, "voted_for": None}
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
