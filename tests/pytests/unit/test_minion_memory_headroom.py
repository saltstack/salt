"""
Tests for the configurable / cgroup-aware ``_has_memory_headroom`` guard on
the minion queue-admission hot path. See issue #69884.
"""

import types

import pytest

import salt.minion

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cgroup_fs(tmp_path, monkeypatch):
    """
    Lay out a synthetic ``/proc/self/cgroup`` + cgroupfs under ``tmp_path``
    and monkey-patch the module-level path constants so the detection helper
    reads from it.

    Returns a callable ``lay(version, limit, current=0, cgroup_path=...)``.
    Callers may invoke it multiple times; later calls overwrite the layout.
    """
    proc_dir = tmp_path / "proc" / "self"
    proc_dir.mkdir(parents=True)
    proc_cgroup = proc_dir / "cgroup"
    fs_root = tmp_path / "sys" / "fs" / "cgroup"
    fs_root.mkdir(parents=True)

    monkeypatch.setattr(salt.minion, "_CGROUP_PROC_PATH", str(proc_cgroup))
    monkeypatch.setattr(salt.minion, "_CGROUP_FS_ROOT", str(fs_root))

    def _lay(version, limit, current=0, cgroup_path="/salt.slice/salt-minion.service"):
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
            # cgroupfs exists but /proc/self/cgroup missing entirely
            if proc_cgroup.exists():
                proc_cgroup.unlink()
        else:
            raise ValueError(f"unknown cgroup version: {version}")

    return _lay


@pytest.fixture
def no_cgroup(tmp_path, monkeypatch):
    """Point the cgroup constants at paths that do not exist."""
    monkeypatch.setattr(
        salt.minion, "_CGROUP_PROC_PATH", str(tmp_path / "nonexistent-cgroup")
    )
    monkeypatch.setattr(
        salt.minion, "_CGROUP_FS_ROOT", str(tmp_path / "nonexistent-fs-root")
    )


def _minion(opts):
    """Return a stand-in with just enough surface for ``_has_memory_headroom``."""
    return types.SimpleNamespace(opts=opts)


# ---------------------------------------------------------------------------
# Parser / helper unit tests
# ---------------------------------------------------------------------------


class TestParseSizeOpt:
    def test_none(self):
        assert salt.minion._parse_size_opt(None) is None

    def test_bool_rejected(self):
        # bool is a subclass of int — must not silently mean 1 byte.
        assert salt.minion._parse_size_opt(True) is None
        assert salt.minion._parse_size_opt(False) is None

    def test_int(self):
        assert salt.minion._parse_size_opt(5368709120) == 5368709120

    def test_zero_and_negative_rejected(self):
        assert salt.minion._parse_size_opt(0) is None
        assert salt.minion._parse_size_opt(-1) is None

    def test_string_digits(self):
        assert salt.minion._parse_size_opt("5368709120") == 5368709120

    def test_string_g(self):
        assert salt.minion._parse_size_opt("5G") == 5 * (1024**3)

    def test_string_m(self):
        assert salt.minion._parse_size_opt("500M") == 500 * (1024**2)

    def test_empty_string(self):
        assert salt.minion._parse_size_opt("") is None
        assert salt.minion._parse_size_opt("   ") is None

    def test_garbage(self):
        assert salt.minion._parse_size_opt("garbage") is None


class TestHeadroomToBytes:
    def test_none(self):
        assert salt.minion._headroom_to_bytes(None, 1024) is None

    def test_percent_5(self):
        # 5% of 2 GB
        assert salt.minion._headroom_to_bytes("5%", 2 * (1024**3)) == int(
            2 * (1024**3) * 0.05
        )

    def test_percent_100(self):
        assert salt.minion._headroom_to_bytes("100%", 1000) == 1000

    def test_percent_zero_rejected(self):
        assert salt.minion._headroom_to_bytes("0%", 1000) is None

    def test_percent_over_100_rejected(self):
        assert salt.minion._headroom_to_bytes("101%", 1000) is None

    def test_percent_garbage_rejected(self):
        assert salt.minion._headroom_to_bytes("abc%", 1000) is None

    def test_size_string(self):
        assert salt.minion._headroom_to_bytes("500M", 999) == 500 * (1024**2)

    def test_int_bytes(self):
        assert salt.minion._headroom_to_bytes(1024, 999) == 1024


class TestParseSelfCgroup:
    def test_v2(self):
        v2, v1 = salt.minion._parse_self_cgroup(
            "0::/system.slice/salt-minion.service\n"
        )
        assert v2 == "/system.slice/salt-minion.service"
        assert v1 is None

    def test_v1_memory(self):
        v2, v1 = salt.minion._parse_self_cgroup(
            "5:memory:/salt.slice\n3:cpu,cpuacct:/user.slice\n"
        )
        assert v2 is None
        assert v1 == "/salt.slice"

    def test_hybrid(self):
        v2, v1 = salt.minion._parse_self_cgroup(
            "0::/user.slice/foo\n5:memory:/salt.slice\n"
        )
        assert v2 == "/user.slice/foo"
        assert v1 == "/salt.slice"

    def test_empty(self):
        assert salt.minion._parse_self_cgroup("") == (None, None)
        assert salt.minion._parse_self_cgroup(None) == (None, None)


# ---------------------------------------------------------------------------
# Cgroup detection
# ---------------------------------------------------------------------------


class TestDetectCgroupMemory:
    def test_no_proc_file(self, no_cgroup):
        assert salt.minion._detect_cgroup_memory() == (None, None, None)

    def test_v2_limited(self, cgroup_fs):
        cgroup_fs("v2", limit=1024**3, current=100 * (1024**2))
        limit, used, source = salt.minion._detect_cgroup_memory()
        assert limit == 1024**3
        assert used == 100 * (1024**2)
        assert source == "cgroup-v2"

    def test_v2_unlimited(self, cgroup_fs):
        cgroup_fs("v2", limit="max")
        assert salt.minion._detect_cgroup_memory() == (None, None, None)

    def test_v1_limited(self, cgroup_fs):
        cgroup_fs("v1", limit=1024**3, current=200 * (1024**2))
        limit, used, source = salt.minion._detect_cgroup_memory()
        assert limit == 1024**3
        assert used == 200 * (1024**2)
        assert source == "cgroup-v1"

    def test_v1_unlimited_sentinel(self, cgroup_fs):
        # Actual kernel sentinel
        cgroup_fs("v1", limit=9223372036854771712)
        assert salt.minion._detect_cgroup_memory() == (None, None, None)


# ---------------------------------------------------------------------------
# _has_memory_headroom matrix
# ---------------------------------------------------------------------------


class TestHasMemoryHeadroom:
    """
    The matrix from the design report. Each case constructs a stand-in
    minion (only ``opts`` needed), lays out a synthetic cgroupfs if the
    scenario calls for one, and mocks ``psutil.virtual_memory`` when the
    scenario cares about system-wide numbers.
    """

    def test_default_below_95(self, no_cgroup, monkeypatch):
        """No config, no cgroup => legacy path, 50% used => True."""
        vm = types.SimpleNamespace(percent=50.0, total=8 * 1024**3, used=4 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        assert salt.minion.Minion._has_memory_headroom(_minion({})) is True

    def test_default_over_95(self, no_cgroup, monkeypatch):
        """No config, no cgroup => legacy path, 96% used => False."""
        vm = types.SimpleNamespace(percent=96.0, total=8 * 1024**3, used=7 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        assert salt.minion.Minion._has_memory_headroom(_minion({})) is False

    def test_config_percent_headroom_pass(self, no_cgroup, monkeypatch):
        """5% headroom, system reference, 90% used => True."""
        total = 100 * 1024**3
        vm = types.SimpleNamespace(percent=90.0, total=total, used=int(total * 0.9))
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"minion_memory_headroom": "5%"}
        assert salt.minion.Minion._has_memory_headroom(_minion(opts)) is True

    def test_config_percent_headroom_fail(self, no_cgroup, monkeypatch):
        """5% headroom, system reference, 96% used => False."""
        total = 100 * 1024**3
        vm = types.SimpleNamespace(percent=96.0, total=total, used=int(total * 0.96))
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"minion_memory_headroom": "5%"}
        assert salt.minion.Minion._has_memory_headroom(_minion(opts)) is False

    def test_config_absolute_headroom(self, no_cgroup, monkeypatch):
        """500 MB headroom on 8 GB host with 7.6 GB used => False."""
        total = 8 * 1024**3
        used = int(7.6 * 1024**3)
        vm = types.SimpleNamespace(percent=95.0, total=total, used=used)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"minion_memory_headroom": "500M"}
        # 500M reserve; 400M free => False
        assert salt.minion.Minion._has_memory_headroom(_minion(opts)) is False

    def test_cgroup_v2_with_no_config_uses_legacy(self, cgroup_fs, monkeypatch):
        """
        Cgroup present but no config => legacy fast path still applies
        (no default flip on LTS). System % determines the result, cgroup
        is ignored.
        """
        cgroup_fs("v2", limit=1024**3, current=990 * (1024**2))
        vm = types.SimpleNamespace(percent=10.0, total=64 * 1024**3, used=6 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        assert salt.minion.Minion._has_memory_headroom(_minion({})) is True

    def test_cgroup_v2_with_config_fails(self, cgroup_fs, monkeypatch):
        """1 GB cgroup, 990 MB used, 5% headroom (~51 MB) => False."""
        cgroup_fs("v2", limit=1024**3, current=990 * (1024**2))
        vm = types.SimpleNamespace(percent=10.0, total=64 * 1024**3, used=6 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"minion_memory_headroom": "5%"}
        assert salt.minion.Minion._has_memory_headroom(_minion(opts)) is False

    def test_cgroup_v2_unlimited_falls_back(self, cgroup_fs, monkeypatch):
        """v2 memory.max == 'max' => fall through to system-wide."""
        cgroup_fs("v2", limit="max")
        # 90% used, 5% headroom => False on the system reference
        total = 8 * 1024**3
        vm = types.SimpleNamespace(percent=90.0, total=total, used=int(total * 0.96))
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"minion_memory_headroom": "5%"}
        assert salt.minion.Minion._has_memory_headroom(_minion(opts)) is False

    def test_cgroup_v1_with_config_passes(self, cgroup_fs, monkeypatch):
        """1 GB v1 cgroup, 200 MB used, 5% headroom => True (800 MB free)."""
        cgroup_fs("v1", limit=1024**3, current=200 * (1024**2))
        vm = types.SimpleNamespace(percent=10.0, total=64 * 1024**3, used=6 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"minion_memory_headroom": "5%"}
        assert salt.minion.Minion._has_memory_headroom(_minion(opts)) is True

    def test_cgroup_v1_unlimited_sentinel_falls_back(self, cgroup_fs, monkeypatch):
        cgroup_fs("v1", limit=9223372036854771712)
        vm = types.SimpleNamespace(percent=50.0, total=8 * 1024**3, used=4 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"minion_memory_headroom": "5%"}
        # Plenty of headroom on system-wide fallback
        assert salt.minion.Minion._has_memory_headroom(_minion(opts)) is True

    def test_config_max_overrides_cgroup(self, cgroup_fs, monkeypatch):
        """
        minion_memory_max wins over cgroup detection. Cgroup says 1 GB
        limit; we pin the reference at 2 GB. With 500 MB reserve and
        200 MB used (cgroup used), 1.3 GB is free of the 2 GB reference.
        """
        cgroup_fs("v2", limit=1024**3, current=200 * (1024**2))
        vm = types.SimpleNamespace(percent=10.0, total=64 * 1024**3, used=6 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {
            "minion_memory_max": "2G",
            "minion_memory_headroom": "500M",
        }
        # 200M used + 500M reserve = 700M < 2G => True
        assert salt.minion.Minion._has_memory_headroom(_minion(opts)) is True

    def test_missing_cgroup_permission_denied_falls_back(self, tmp_path, monkeypatch):
        """
        Cgroup files exist but reads fail (simulated via unreadable path).
        Must not raise; must fall back to system-wide arithmetic.
        """
        # Point at a path that surely can't be read: use a directory as the
        # cgroup file so open() will raise IsADirectoryError.
        bad_path = tmp_path / "cgroup-is-a-dir"
        bad_path.mkdir()
        monkeypatch.setattr(salt.minion, "_CGROUP_PROC_PATH", str(bad_path))
        monkeypatch.setattr(salt.minion, "_CGROUP_FS_ROOT", str(tmp_path))
        vm = types.SimpleNamespace(percent=50.0, total=8 * 1024**3, used=4 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"minion_memory_headroom": "5%"}
        # 5% of 8G reserve is ~410M. 4G used + 410M = 4.4G < 8G => True.
        assert salt.minion.Minion._has_memory_headroom(_minion(opts)) is True

    def test_no_psutil_returns_true(self, monkeypatch):
        monkeypatch.setattr(salt.minion, "HAS_PSUTIL", False)
        opts = {"minion_memory_headroom": "5%"}
        assert salt.minion.Minion._has_memory_headroom(_minion(opts)) is True

    def test_bogus_headroom_string_does_not_raise(self, no_cgroup, monkeypatch):
        """
        Bogus opt value must not raise. It should DEBUG-log and fall back
        to an implicit 5% reserve on the resolved reference so the operator's
        intent to opt in is still honored.
        """
        total = 8 * 1024**3
        vm = types.SimpleNamespace(percent=50.0, total=total, used=4 * 1024**3)
        monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
        opts = {"minion_memory_headroom": "garbage"}
        # 5% of 8G = 410M implicit; 4G + 410M = 4.4G < 8G => True.
        assert salt.minion.Minion._has_memory_headroom(_minion(opts)) is True
