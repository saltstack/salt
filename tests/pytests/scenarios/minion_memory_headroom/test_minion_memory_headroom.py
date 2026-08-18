"""
End-to-end scenario tests for the opt-in ``minion_memory_headroom`` /
``minion_memory_max`` minion config options and the runtime path through
``salt.minion.Minion._has_memory_headroom``.

These complement the unit-level matrix in
``tests/pytests/unit/test_minion_memory_headroom.py`` (which mocks psutil
and injects a synthetic cgroupfs). Here we boot a real minion daemon with
each opt combination and drive the check via subprocess evaluation of the
minion's on-disk config, proving the loader accepts the new opts and the
runtime code path returns the expected value.

See issue https://github.com/saltstack/salt/issues/69884.
"""

import subprocess
import sys
import textwrap

import pytest

pytestmark = [
    pytest.mark.slow_test,
]


def _run_headroom_eval(config_path):
    """
    Spawn a subprocess in the same Python interpreter that pytest is running
    under, load the minion config from ``config_path``, construct an
    ``SMinion``, and print the JSON-serialisable result of
    ``_has_memory_headroom()``.

    Returns the string printed (``"True"`` or ``"False"``). Raises with the
    subprocess stderr on any failure so debugging is straightforward.
    """
    # ``_has_memory_headroom`` is defined on ``Minion`` (not ``SMinion``)
    # and only reads ``self.opts``. Rather than constructing a full
    # ``Minion`` (which requires master connectivity and a running loop),
    # bind the unbound method to a ``SimpleNamespace`` carrying the loaded
    # opts. This exercises the exact code path the running minion daemon
    # takes: it loads the config from disk via ``salt.config.minion_config``
    # and calls ``Minion._has_memory_headroom``.
    script = textwrap.dedent(
        f"""
        import types
        import salt.config
        import salt.minion
        opts = salt.config.minion_config({config_path!r})
        stub = types.SimpleNamespace(opts=opts)
        print(salt.minion.Minion._has_memory_headroom(stub))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"headroom-eval subprocess failed (rc={result.returncode})\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result.stdout.strip().splitlines()[-1]


# ---------------------------------------------------------------------------
# Scenario 1: opts round-trip through the config loader
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "minion_with_opts",
    [{"minion_memory_headroom": "5G", "minion_memory_max": "10G"}],
    indirect=True,
    ids=["headroom-5g-max-10g"],
)
def test_config_round_trip(minion_with_opts):
    """
    Boot a minion with the new opts in its config file, then use
    ``salt-call --local config.get`` to read them back. Proves the loader
    accepts both opts (i.e. they're in ``VALID_OPTS``) and that they
    survive the write-file / read-file round trip.
    """
    salt_call = minion_with_opts.salt_call_cli()
    ret = salt_call.run("--local", "config.get", "minion_memory_headroom")
    assert ret.returncode == 0, ret
    assert ret.data == "5G"

    ret = salt_call.run("--local", "config.get", "minion_memory_max")
    assert ret.returncode == 0, ret
    assert ret.data == "10G"


# ---------------------------------------------------------------------------
# Scenario 2: default preserved end-to-end (no upgrade drift)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "minion_with_opts",
    [{}],
    indirect=True,
    ids=["defaults"],
)
def test_default_preserved(minion_with_opts):
    """
    With neither ``minion_memory_headroom`` nor ``minion_memory_max`` set,
    the runtime check must return the legacy ``psutil.virtual_memory()
    .percent > 95`` verdict. On any test host that has more than 5% RAM
    free (a safe assumption) the result is True.
    """
    # Runtime path: legacy branch. Any healthy CI host has >5% RAM free.
    result = _run_headroom_eval(minion_with_opts.config_file)
    assert result == "True"


# ---------------------------------------------------------------------------
# Scenario 3: config override forces a deterministic-True result
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "minion_with_opts",
    [
        {
            # 1 EB pinned as reference; 1% headroom (~10 PB). No matter
            # what the actual system usage looks like, used+headroom
            # is nowhere near 1 EB, so the check must return True.
            "minion_memory_max": 1 << 60,
            "minion_memory_headroom": "1%",
        }
    ],
    indirect=True,
    ids=["huge-max-tiny-percent"],
)
def test_config_override_deterministic_true(minion_with_opts):
    """
    With ``minion_memory_max = 1 EB`` and ``minion_memory_headroom = "1%"``
    the runtime check is guaranteed to return True regardless of actual
    system memory pressure. Proves the config path drives real
    ``_has_memory_headroom()`` behavior.
    """
    result = _run_headroom_eval(minion_with_opts.config_file)
    assert result == "True"


# ---------------------------------------------------------------------------
# Scenario 4: config override forces a deterministic-False result
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "minion_with_opts",
    [
        {
            # 1 KB pinned as reference; 100% headroom means "reserve
            # everything". used + headroom > reference is guaranteed
            # (unless the process has literally 0 bytes RSS, which is
            # impossible).
            "minion_memory_max": 1024,
            "minion_memory_headroom": "100%",
        }
    ],
    indirect=True,
    ids=["tiny-max-full-percent"],
)
def test_config_override_deterministic_false(minion_with_opts):
    """
    With ``minion_memory_max = 1 KB`` and ``minion_memory_headroom = "100%"``
    the runtime check is guaranteed to return False. Proves the config
    path can actually block queue admission when the operator asks it to.
    """
    result = _run_headroom_eval(minion_with_opts.config_file)
    assert result == "False"
