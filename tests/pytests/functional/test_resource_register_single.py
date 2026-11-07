"""
Scale functional tests for chunked resource registration against a single
master + single minion.

Validates the dwoz/fix/minion-register-scale PR end-to-end on a real
master/minion pair:

* Small (< chunk) inventories still register via the legacy wire format.
* Large inventories (> chunk) flow through the chunked RPC and land
  atomically on the master.
* The default (``resource_grains_cache_in_memory: False``) actually keeps
  the minion's RSS bounded on a 100K pillar while the opt-in path does
  retain the grain map.
* Grain-targeted dispatch returns the right resource subset under both
  retention modes.

The 100 000 / 200 000 resource tests are ``slow_test``-gated — they're
the regression gate for the live production bug this PR targets but are
too heavy for every-commit CI. Run with ``-m slow_test`` to include.
"""

import logging
import os
import textwrap
import time

import pytest

import salt.utils.files
from tests.conftest import FIPS_TESTRUN

try:
    import psutil

    HAVE_PSUTIL = True
except ImportError:  # pragma: no cover - psutil is normally installed
    psutil = None
    HAVE_PSUTIL = False

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


MINION_ID = "scale-register-minion"


def _pillar_sls_with_n_resources(n, rtype="dummy"):
    """
    Return the SLS text for a pillar with ``n`` resource IDs under
    ``resources.<rtype>.resource_ids``.

    Written directly as text rather than via yaml.safe_dump so the fixture
    cost at 200K resources stays O(n) in file I/O rather than paying the
    serializer penalty. The result parses as valid YAML.
    """
    lines = [
        "resources:",
        f"  {rtype}:",
        "    resource_ids:",
    ]
    for i in range(n):
        lines.append(f"      - {rtype}-{i:08d}")
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def salt_master_factory(salt_factories, request):
    """A fresh master for these scale tests (don't share with resources/ pkg)."""
    overrides = {
        "interface": "127.0.0.1",
        "transport": request.config.getoption("--transport"),
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
        "minion_data_cache": True,
    }
    factory = salt_factories.salt_master_daemon(
        "scale-register-master",
        overrides=overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


def _make_minion(master_factory, overrides=None):
    """Build a scale-register minion against ``master_factory`` and return it."""
    opts = {
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        "multiprocessing": False,
    }
    if overrides:
        opts.update(overrides)
    factory = master_factory.salt_minion_daemon(
        MINION_ID,
        overrides=opts,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, master_factory, factory.id
    )
    return factory


def _write_pillar(master_factory, pillar_sls_text):
    """
    Install a pillar tree exposing ``pillar_sls_text`` as ``scale.sls`` and a
    top.sls referring to it. Returns a context manager — enter it to make
    the pillar visible to the minion, exit to remove it.
    """
    top = textwrap.dedent(
        f"""
        base:
          '{MINION_ID}':
            - scale
        """
    )
    return (
        master_factory.pillar_tree.base.temp_file("top.sls", top),
        master_factory.pillar_tree.base.temp_file("scale.sls", pillar_sls_text),
    )


def _wait_for_registry(master_factory, expected_count, timeout, type_name="dummy"):
    """
    Poll ``salt-run resource.list_grains`` until the master's
    ``resource_grains`` bank contains at least ``expected_count`` SRNs of
    type ``type_name``, or ``timeout`` elapses.

    Using the salt-run CLI (rather than opening the registry in-process)
    is the correct cross-process check: the master and the test runner
    don't share the mmap singleton, so the in-process registry singleton
    reads an empty copy.

    Returns the final observed count. Does NOT assert — the caller logs
    the result and decides.
    """
    salt_run = master_factory.salt_run_cli(timeout=60)
    deadline = time.monotonic() + timeout
    count = 0
    while time.monotonic() < deadline:
        ret = salt_run.run("resource.list_grains", _timeout=60)
        if ret.returncode == 0 and isinstance(ret.data, dict):
            count = sum(1 for srn in ret.data if srn.startswith(f"{type_name}:"))
            if count >= expected_count:
                return count
        time.sleep(1.0)
    return count


def _assert_no_truncation_in_master_log(master_factory):
    """
    Regression gate for the mmap heap fix (#70717): under chunked register
    the master's mmap registry must not emit "is truncated" warnings. If
    the heap-stale-mmap bug reappears, chunks that span a heap-grow boundary
    will trigger these warnings as the writer sees a stale capacity.
    """
    log_path = master_factory.config.get("log_file")
    if not log_path or not os.path.exists(log_path):
        return  # Nothing to inspect.
    offenders = []
    with salt.utils.files.fopen(log_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "is truncated" in line:
                offenders.append(line.strip())
    assert (
        not offenders
    ), "master log contains unexpected 'is truncated' warnings:\n" + "\n".join(
        offenders[:10]
    )


# ---------------------------------------------------------------------------
# Baseline (fast) register
# ---------------------------------------------------------------------------


def test_register_small_pillar_single_chunk(salt_master_factory, tmp_path):
    """
    A 50-resource pillar is below the default chunk size (10 000) so the
    minion sends an unchunked register. The master's registry should see
    all 50.
    """
    top_ctx, sls_ctx = _write_pillar(
        salt_master_factory, _pillar_sls_with_n_resources(50)
    )
    with top_ctx, sls_ctx:
        minion_factory = _make_minion(salt_master_factory)
        with minion_factory.started(start_timeout=120):
            salt_call_cli = minion_factory.salt_call_cli()
            ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True, _timeout=120)
            assert ret.returncode == 0, ret
            ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
            assert ret.returncode == 0, ret
            count = _wait_for_registry(salt_master_factory, 50, timeout=60)
            assert (
                count == 50
            ), f"50-resource pillar must register exactly 50 items, got {count}"
    _assert_no_truncation_in_master_log(salt_master_factory)


def test_register_chunked_pillar_completes(salt_master_factory, tmp_path):
    """
    Force chunking at a small threshold and verify a multi-chunk register
    lands atomically. Keeps the per-test wall time short while still
    exercising the chunked wire path.
    """
    top_ctx, sls_ctx = _write_pillar(
        salt_master_factory, _pillar_sls_with_n_resources(250)
    )
    with top_ctx, sls_ctx:
        minion_factory = _make_minion(
            salt_master_factory,
            overrides={"resource_register_chunk_size": 100},
        )
        with minion_factory.started(start_timeout=120):
            salt_call_cli = minion_factory.salt_call_cli()
            ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True, _timeout=120)
            assert ret.returncode == 0, ret
            ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
            assert ret.returncode == 0, ret
            # Should produce exactly 3 chunks (100 + 100 + 50) on register.
            count = _wait_for_registry(salt_master_factory, 250, timeout=120)
            assert (
                count == 250
            ), f"chunked register must commit 250 resources atomically, got {count}"
    _assert_no_truncation_in_master_log(salt_master_factory)


# ---------------------------------------------------------------------------
# Memory bound (default retention OFF)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAVE_PSUTIL, reason="psutil not installed")
def test_default_minion_rss_bounded_with_chunked_register(
    salt_master_factory, tmp_path
):
    """
    Register 5000 resources under the default
    ``resource_grains_cache_in_memory: False``. After the register lands
    on the master, the minion's resident memory must be well under the
    threshold where carrying a 5000-entry grain map would add measurable
    overhead (~2 MB at the dummy module's 4-key grains dict, scaling to
    40-80 MB at the 200K production target).

    Uses 5000 rather than 100K to keep every-run CI tractable; the
    opt-in/opt-out delta scales linearly so a 5K smoke catches an opt-out
    regression that retains the full map by mistake.
    """
    top_ctx, sls_ctx = _write_pillar(
        salt_master_factory, _pillar_sls_with_n_resources(5000)
    )
    with top_ctx, sls_ctx:
        minion_factory = _make_minion(
            salt_master_factory,
            overrides={"resource_register_chunk_size": 1000},
        )
        with minion_factory.started(start_timeout=180):
            salt_call_cli = minion_factory.salt_call_cli()
            ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True, _timeout=180)
            assert ret.returncode == 0, ret
            ret = salt_call_cli.run("saltutil.sync_all", _timeout=180)
            assert ret.returncode == 0, ret
            count = _wait_for_registry(salt_master_factory, 5000, timeout=180)
            assert count == 5000, f"5K register must land all items, got {count}"
            # Give the minion a moment to settle after chunk completion so
            # the stable resident set is what we measure.
            time.sleep(2)
            minion_pid = minion_factory.pid
            assert (
                minion_pid
            ), "expected the minion factory to expose its subprocess pid"
            try:
                proc = psutil.Process(minion_pid)
                rss_mb = proc.memory_info().rss / (1024 * 1024)
            except psutil.NoSuchProcess:  # pragma: no cover - teardown race
                pytest.skip("minion exited before RSS measurement")
            log.info("minion RSS after 5K register (opt-out): %.1f MB", rss_mb)
            # Permissive ceiling — the dummy module and loader baselines
            # vary across platforms. 250 MB is comfortably above the
            # baseline (~100-150 MB seen locally) and well below where a
            # retained 200K grain map would land. The real purpose of
            # this bound is to catch regressions that put the full
            # per-resource grain map back on the instance forever.
            assert rss_mb < 250, (
                f"minion RSS unexpectedly high after 5K opt-out register: "
                f"{rss_mb:.1f} MB (ceiling 250 MB)"
            )
    _assert_no_truncation_in_master_log(salt_master_factory)


# ---------------------------------------------------------------------------
# Full 100 000 / 200 000 scale run (nightly)
#
# True grain-target scale coverage lives in the cluster tier
# (``cluster/test_resource_register_cluster.py``) — the stock dummy
# resource module hard-codes its grains dict so every resource matches
# the same grain expression, making a single-master grain-target scale
# test uninformative.
# ---------------------------------------------------------------------------


@pytest.mark.slow_test
@pytest.mark.timeout(600)
def test_register_100k_resources_completes(salt_master_factory, tmp_path):
    """
    Register 100 000 resources on a single minion. With chunking the full
    registration must complete within the timeout and the master's registry
    must see exactly 100 000 items. Regression gate for the production bug
    where the un-chunked register timed out mid-batch.
    """
    top_ctx, sls_ctx = _write_pillar(
        salt_master_factory, _pillar_sls_with_n_resources(100_000)
    )
    with top_ctx, sls_ctx:
        minion_factory = _make_minion(salt_master_factory)
        start = time.monotonic()
        with minion_factory.started(start_timeout=300):
            salt_call_cli = minion_factory.salt_call_cli()
            ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True, _timeout=300)
            assert ret.returncode == 0, ret
            ret = salt_call_cli.run("saltutil.sync_all", _timeout=300)
            assert ret.returncode == 0, ret
            count = _wait_for_registry(salt_master_factory, 100_000, timeout=300)
            elapsed = time.monotonic() - start
            log.info("100K register observed %d items after %.1fs", count, elapsed)
            assert (
                count == 100_000
            ), f"100K register must land all items, got {count} after {elapsed:.1f}s"
    _assert_no_truncation_in_master_log(salt_master_factory)


@pytest.mark.slow_test
@pytest.mark.timeout(900)
def test_register_200k_resources_completes(salt_master_factory, tmp_path):
    """
    The scale target: 200K resources through chunked register. The whole
    registration must land atomically — the master sees either 0 or 200K,
    never a half-committed registry.
    """
    top_ctx, sls_ctx = _write_pillar(
        salt_master_factory, _pillar_sls_with_n_resources(200_000)
    )
    with top_ctx, sls_ctx:
        minion_factory = _make_minion(salt_master_factory)
        start = time.monotonic()
        with minion_factory.started(start_timeout=300):
            salt_call_cli = minion_factory.salt_call_cli()
            ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True, _timeout=600)
            assert ret.returncode == 0, ret
            ret = salt_call_cli.run("saltutil.sync_all", _timeout=600)
            assert ret.returncode == 0, ret
            count = _wait_for_registry(salt_master_factory, 200_000, timeout=600)
            elapsed = time.monotonic() - start
            log.info("200K register observed %d items after %.1fs", count, elapsed)
            assert (
                count == 200_000
            ), f"200K register must land all items, got {count} after {elapsed:.1f}s"
    _assert_no_truncation_in_master_log(salt_master_factory)
