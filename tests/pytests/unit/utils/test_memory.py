"""
Tests for :mod:`salt.utils.memory` — the cgroup-aware memory-headroom
helpers used by the opt-in EventPublisher / MWorkerQueue backpressure
gates added in PR #70053 and the minion-side check in #70038.

The parser + cgroup-detection test patterns mirror
``tests/pytests/unit/test_minion_memory_headroom.py`` in PR #70038 so
both call sites converge on the same behavioral contract.
"""

import logging
import types

import pytest

import salt.utils.memory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cgroup_fs(tmp_path, monkeypatch):
    """
    Lay out a synthetic ``/proc/self/cgroup`` + cgroupfs under ``tmp_path``
    and monkey-patch the module-level path constants so the detection
    helper reads from it.

    Returns a callable ``lay(version, limit, current=0, cgroup_path=...)``.
    Callers may invoke it multiple times; later calls overwrite the layout.
    """
    proc_dir = tmp_path / "proc" / "self"
    proc_dir.mkdir(parents=True)
    proc_cgroup = proc_dir / "cgroup"
    fs_root = tmp_path / "sys" / "fs" / "cgroup"
    fs_root.mkdir(parents=True)

    monkeypatch.setattr(salt.utils.memory, "_CGROUP_PROC_PATH", str(proc_cgroup))
    monkeypatch.setattr(salt.utils.memory, "_CGROUP_FS_ROOT", str(fs_root))

    def _lay(version, limit, current=0, cgroup_path="/salt.slice/salt-master.service"):
        if version == "v2":
            proc_cgroup.write_text(f"0::{cgroup_path}\n")
            unit_dir = fs_root / cgroup_path.lstrip("/")
            unit_dir.mkdir(parents=True, exist_ok=True)
            limit_str = "max" if limit == "max" else str(limit)
            (unit_dir / "memory.max").write_text(limit_str + "\n")
            (unit_dir / "memory.current").write_text(str(current) + "\n")
        elif version == "v1":
            proc_cgroup.write_text(
                f"5:memory:{cgroup_path}\n2:cpu,cpuacct:{cgroup_path}\n"
            )
            unit_dir = fs_root / "memory" / cgroup_path.lstrip("/")
            unit_dir.mkdir(parents=True, exist_ok=True)
            (unit_dir / "memory.limit_in_bytes").write_text(str(limit) + "\n")
            (unit_dir / "memory.usage_in_bytes").write_text(str(current) + "\n")
        elif version == "none":
            if proc_cgroup.exists():
                proc_cgroup.unlink()
        else:
            raise ValueError(f"unknown cgroup version: {version}")

    return _lay


@pytest.fixture
def no_cgroup(tmp_path, monkeypatch):
    """Point the cgroup constants at paths that do not exist."""
    monkeypatch.setattr(
        salt.utils.memory,
        "_CGROUP_PROC_PATH",
        str(tmp_path / "nonexistent-cgroup"),
    )
    monkeypatch.setattr(
        salt.utils.memory,
        "_CGROUP_FS_ROOT",
        str(tmp_path / "nonexistent-fs-root"),
    )


# ---------------------------------------------------------------------------
# parse_size
# ---------------------------------------------------------------------------


class TestParseSize:
    def test_none(self):
        assert salt.utils.memory.parse_size(None) is None

    def test_bool_rejected(self):
        # bool is a subclass of int — must not silently mean 1 byte.
        assert salt.utils.memory.parse_size(True) is None
        assert salt.utils.memory.parse_size(False) is None

    def test_int(self):
        assert salt.utils.memory.parse_size(5368709120) == 5368709120

    def test_zero_and_negative_rejected(self):
        assert salt.utils.memory.parse_size(0) is None
        assert salt.utils.memory.parse_size(-1) is None

    def test_string_digits(self):
        assert salt.utils.memory.parse_size("5368709120") == 5368709120

    def test_string_g(self):
        assert salt.utils.memory.parse_size("5G") == 5 * (1024**3)

    def test_string_m(self):
        assert salt.utils.memory.parse_size("500M") == 500 * (1024**2)

    def test_empty_string(self):
        assert salt.utils.memory.parse_size("") is None
        assert salt.utils.memory.parse_size("   ") is None

    def test_garbage(self):
        assert salt.utils.memory.parse_size("garbage") is None

    def test_non_str_non_int(self):
        assert salt.utils.memory.parse_size([1024]) is None
        assert salt.utils.memory.parse_size({"bytes": 1024}) is None
        assert salt.utils.memory.parse_size(1.5) is None


# ---------------------------------------------------------------------------
# parse_headroom
# ---------------------------------------------------------------------------


class TestParseHeadroom:
    def test_none(self):
        assert salt.utils.memory.parse_headroom(None, 1024) is None

    def test_percent_5(self):
        assert salt.utils.memory.parse_headroom("5%", 2 * (1024**3)) == int(
            2 * (1024**3) * 0.05
        )

    def test_percent_100(self):
        assert salt.utils.memory.parse_headroom("100%", 1000) == 1000

    def test_percent_zero_rejected(self):
        assert salt.utils.memory.parse_headroom("0%", 1000) is None

    def test_percent_over_100_rejected(self):
        assert salt.utils.memory.parse_headroom("101%", 1000) is None

    def test_percent_garbage_rejected(self):
        assert salt.utils.memory.parse_headroom("abc%", 1000) is None

    def test_size_string(self):
        assert salt.utils.memory.parse_headroom("500M", 999) == 500 * (1024**2)

    def test_int_bytes(self):
        assert salt.utils.memory.parse_headroom(1024, 999) == 1024

    def test_percent_with_surrounding_whitespace(self):
        assert salt.utils.memory.parse_headroom("  5%  ", 1000) == 50


# ---------------------------------------------------------------------------
# _read_cgroup_file
# ---------------------------------------------------------------------------


class TestReadCgroupFile:
    def test_missing_returns_none(self, tmp_path):
        assert salt.utils.memory._read_cgroup_file(str(tmp_path / "nope")) is None

    def test_permission_denied_returns_none(self, tmp_path):
        # A directory as the path will raise IsADirectoryError on open("r").
        d = tmp_path / "adir"
        d.mkdir()
        assert salt.utils.memory._read_cgroup_file(str(d)) is None

    def test_returns_stripped_content(self, tmp_path):
        p = tmp_path / "value"
        p.write_text("  1073741824\n")
        assert salt.utils.memory._read_cgroup_file(str(p)) == "1073741824"


# ---------------------------------------------------------------------------
# _parse_self_cgroup
# ---------------------------------------------------------------------------


class TestParseSelfCgroup:
    def test_v2(self):
        v2, v1 = salt.utils.memory._parse_self_cgroup(
            "0::/system.slice/salt-master.service\n"
        )
        assert v2 == "/system.slice/salt-master.service"
        assert v1 is None

    def test_v1_memory(self):
        v2, v1 = salt.utils.memory._parse_self_cgroup(
            "5:memory:/salt.slice\n3:cpu,cpuacct:/user.slice\n"
        )
        assert v2 is None
        assert v1 == "/salt.slice"

    def test_hybrid(self):
        v2, v1 = salt.utils.memory._parse_self_cgroup(
            "0::/user.slice/foo\n5:memory:/salt.slice\n"
        )
        assert v2 == "/user.slice/foo"
        assert v1 == "/salt.slice"

    def test_empty(self):
        assert salt.utils.memory._parse_self_cgroup("") == (None, None)
        assert salt.utils.memory._parse_self_cgroup(None) == (None, None)

    def test_malformed_lines_skipped(self):
        v2, v1 = salt.utils.memory._parse_self_cgroup(
            "not-a-cgroup-line\n0::/only-good-line\ngarbage:foo\n"
        )
        assert v2 == "/only-good-line"
        assert v1 is None

    def test_memory_in_multiple_controllers(self):
        # comma-separated controller list must be split on ',' — a naive
        # substring check would false-positive on "memoryhog" etc.
        v2, v1 = salt.utils.memory._parse_self_cgroup(
            "9:cpu,memory,pids:/salt.slice/x\n"
        )
        assert v2 is None
        assert v1 == "/salt.slice/x"

    def test_empty_cgroup_path_becomes_root(self):
        v2, v1 = salt.utils.memory._parse_self_cgroup("0::\n5:memory:\n")
        assert v2 == "/"
        assert v1 == "/"


# ---------------------------------------------------------------------------
# _detect_cgroup_memory
# ---------------------------------------------------------------------------


class TestDetectCgroupMemory:
    def test_no_proc_file(self, no_cgroup):
        assert salt.utils.memory._detect_cgroup_memory() == (None, None, None)

    def test_v2_limited(self, cgroup_fs):
        cgroup_fs("v2", limit=1024**3, current=100 * (1024**2))
        limit, used, source = salt.utils.memory._detect_cgroup_memory()
        assert limit == 1024**3
        assert used == 100 * (1024**2)
        assert source == "cgroup-v2"

    def test_v2_unlimited_max_sentinel(self, cgroup_fs):
        cgroup_fs("v2", limit="max")
        assert salt.utils.memory._detect_cgroup_memory() == (None, None, None)

    def test_v1_limited(self, cgroup_fs):
        cgroup_fs("v1", limit=1024**3, current=200 * (1024**2))
        limit, used, source = salt.utils.memory._detect_cgroup_memory()
        assert limit == 1024**3
        assert used == 200 * (1024**2)
        assert source == "cgroup-v1"

    def test_v1_unlimited_sentinel(self, cgroup_fs):
        # Actual kernel sentinel (~9.22 EB)
        cgroup_fs("v1", limit=9223372036854771712)
        assert salt.utils.memory._detect_cgroup_memory() == (None, None, None)

    def test_v2_missing_files_falls_through(self, tmp_path, monkeypatch):
        # /proc/self/cgroup points at a v2 path but the cgroupfs entry is
        # absent — detection must return (None, None, None) rather than raising.
        proc_dir = tmp_path / "proc" / "self"
        proc_dir.mkdir(parents=True)
        proc_cgroup = proc_dir / "cgroup"
        proc_cgroup.write_text("0::/does-not-exist\n")
        fs_root = tmp_path / "sys" / "fs" / "cgroup"
        fs_root.mkdir(parents=True)
        monkeypatch.setattr(salt.utils.memory, "_CGROUP_PROC_PATH", str(proc_cgroup))
        monkeypatch.setattr(salt.utils.memory, "_CGROUP_FS_ROOT", str(fs_root))
        assert salt.utils.memory._detect_cgroup_memory() == (None, None, None)


# ---------------------------------------------------------------------------
# resolve_memory_reference
# ---------------------------------------------------------------------------


class TestResolveMemoryReference:
    def test_config_max_wins_over_cgroup(self, cgroup_fs, monkeypatch):
        cgroup_fs("v2", limit=1024**3, current=200 * (1024**2))
        vm = types.SimpleNamespace(total=64 * 1024**3, used=6 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        ref, used, source = salt.utils.memory.resolve_memory_reference("2G")
        assert ref == 2 * 1024**3
        # cgroup used (200 MB) preferred over vm.used when cgroup available
        assert used == 200 * (1024**2)
        assert source == "config"

    def test_config_max_used_falls_back_to_vm_when_no_cgroup(
        self, no_cgroup, monkeypatch
    ):
        vm = types.SimpleNamespace(total=8 * 1024**3, used=4 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        ref, used, source = salt.utils.memory.resolve_memory_reference("1G")
        assert ref == 1024**3
        assert used == 4 * 1024**3
        assert source == "config"

    def test_cgroup_v2_when_no_config(self, cgroup_fs, monkeypatch):
        cgroup_fs("v2", limit=1024**3, current=100 * (1024**2))
        vm = types.SimpleNamespace(total=64 * 1024**3, used=6 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        ref, used, source = salt.utils.memory.resolve_memory_reference(None)
        assert ref == 1024**3
        assert used == 100 * (1024**2)
        assert source == "cgroup-v2"

    def test_cgroup_v1_when_no_config(self, cgroup_fs, monkeypatch):
        cgroup_fs("v1", limit=1024**3, current=200 * (1024**2))
        vm = types.SimpleNamespace(total=64 * 1024**3, used=6 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        ref, used, source = salt.utils.memory.resolve_memory_reference(None)
        assert ref == 1024**3
        assert used == 200 * (1024**2)
        assert source == "cgroup-v1"

    def test_system_fallback(self, no_cgroup, monkeypatch):
        vm = types.SimpleNamespace(total=8 * 1024**3, used=4 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        ref, used, source = salt.utils.memory.resolve_memory_reference(None)
        assert ref == 8 * 1024**3
        assert used == 4 * 1024**3
        assert source == "system"

    def test_unparseable_max_falls_through(self, cgroup_fs, monkeypatch):
        cgroup_fs("v2", limit=1024**3, current=100 * (1024**2))
        vm = types.SimpleNamespace(total=64 * 1024**3, used=6 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        # garbage max_opt → parse_size returns None → fall through to cgroup
        ref, used, source = salt.utils.memory.resolve_memory_reference("garbage")
        assert ref == 1024**3
        assert source == "cgroup-v2"


# ---------------------------------------------------------------------------
# has_memory_headroom
# ---------------------------------------------------------------------------


class TestHasMemoryHeadroom:
    def test_both_opts_none_returns_true(self, no_cgroup, monkeypatch):
        # No config, so no check runs at all; result must be True even
        # if the system is under memory pressure.
        vm = types.SimpleNamespace(total=8 * 1024**3, used=int(7.9 * 1024**3))
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        assert (
            salt.utils.memory.has_memory_headroom(
                {},
                "event_publisher_memory_headroom",
                "event_publisher_memory_max",
            )
            is True
        )

    def test_missing_psutil_returns_true(self, monkeypatch):
        # Simulate ImportError on ``import psutil``. builtins.__import__
        # is safer than trying to remove psutil from sys.modules mid-test.
        import builtins

        real_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name == "psutil":
                raise ImportError("no psutil")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _fake_import)
        opts = {"event_publisher_memory_headroom": "5%"}
        assert (
            salt.utils.memory.has_memory_headroom(
                opts,
                "event_publisher_memory_headroom",
                "event_publisher_memory_max",
            )
            is True
        )

    def test_over_limit_returns_false_and_warns(self, no_cgroup, monkeypatch, caplog):
        total = 8 * 1024**3
        vm = types.SimpleNamespace(total=total, used=int(total * 0.99))
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"event_publisher_memory_headroom": "5%"}
        with caplog.at_level(logging.WARNING, logger="salt.utils.memory"):
            result = salt.utils.memory.has_memory_headroom(
                opts,
                "event_publisher_memory_headroom",
                "event_publisher_memory_max",
                subject="EventPublisher",
            )
        assert result is False
        assert "EventPublisher" in caplog.text
        assert "headroom exhausted" in caplog.text

    def test_under_limit_returns_true(self, no_cgroup, monkeypatch):
        total = 8 * 1024**3
        vm = types.SimpleNamespace(total=total, used=int(total * 0.5))
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"event_publisher_memory_headroom": "5%"}
        assert (
            salt.utils.memory.has_memory_headroom(
                opts,
                "event_publisher_memory_headroom",
                "event_publisher_memory_max",
            )
            is True
        )

    def test_bogus_headroom_falls_back_to_5_percent(self, no_cgroup, monkeypatch):
        # Bogus opt value should not raise; falls back to 5% of the
        # resolved reference so the operator's intent to opt in is honored.
        total = 8 * 1024**3
        vm = types.SimpleNamespace(total=total, used=int(total * 0.5))
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"event_publisher_memory_headroom": "garbage"}
        # 4 GB used + 5% of 8 GB reserve (~410 MB) = 4.4 GB < 8 GB => True.
        assert (
            salt.utils.memory.has_memory_headroom(
                opts,
                "event_publisher_memory_headroom",
                "event_publisher_memory_max",
            )
            is True
        )

    def test_bogus_headroom_falls_back_and_can_fail(self, no_cgroup, monkeypatch):
        # Same 5% fallback, but with 99% used → fails.
        total = 8 * 1024**3
        vm = types.SimpleNamespace(total=total, used=int(total * 0.99))
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"event_publisher_memory_headroom": "garbage"}
        assert (
            salt.utils.memory.has_memory_headroom(
                opts,
                "event_publisher_memory_headroom",
                "event_publisher_memory_max",
            )
            is False
        )

    def test_max_only_no_headroom_uses_5_percent(self, no_cgroup, monkeypatch):
        # Only max is set, headroom None → parse_headroom(None, ...) returns
        # None → fall back to 5% of the (configured) reference.
        vm = types.SimpleNamespace(total=64 * 1024**3, used=200 * (1024**2))
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"event_publisher_memory_max": "1G"}
        # ref=1G, 5% headroom=~51M, used=200M → 200M + 51M = 251M < 1G → True.
        assert (
            salt.utils.memory.has_memory_headroom(
                opts,
                "event_publisher_memory_headroom",
                "event_publisher_memory_max",
            )
            is True
        )

    def test_max_only_over_limit_fails(self, cgroup_fs, monkeypatch):
        # max=1G reference; cgroup reports used=990M; 5% fallback ~51M →
        # 990M + 51M > 1G → False.
        cgroup_fs("v2", limit=2 * 1024**3, current=990 * (1024**2))
        vm = types.SimpleNamespace(total=64 * 1024**3, used=6 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"event_publisher_memory_max": "1G"}
        assert (
            salt.utils.memory.has_memory_headroom(
                opts,
                "event_publisher_memory_headroom",
                "event_publisher_memory_max",
            )
            is False
        )

    def test_subject_defaults_to_headroom_opt_key(self, no_cgroup, monkeypatch, caplog):
        total = 8 * 1024**3
        vm = types.SimpleNamespace(total=total, used=int(total * 0.99))
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"mworker_queue_memory_headroom": "5%"}
        with caplog.at_level(logging.WARNING, logger="salt.utils.memory"):
            salt.utils.memory.has_memory_headroom(
                opts,
                "mworker_queue_memory_headroom",
                "mworker_queue_memory_max",
            )
        assert "mworker_queue_memory_headroom" in caplog.text

    def test_exception_in_resolve_returns_true(self, no_cgroup, monkeypatch):
        # Exceptions from resolve_memory_reference must be swallowed so
        # the check remains a safety valve and never becomes a new failure
        # mode. Force psutil.virtual_memory to raise.
        def _boom():
            raise RuntimeError("psutil exploded")

        monkeypatch.setattr("psutil.virtual_memory", _boom)
        opts = {"event_publisher_memory_headroom": "5%"}
        assert (
            salt.utils.memory.has_memory_headroom(
                opts,
                "event_publisher_memory_headroom",
                "event_publisher_memory_max",
            )
            is True
        )
