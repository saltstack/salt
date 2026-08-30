"""
Concurrency + integration coverage for the async ``MWorker`` request path.

Background
----------
26 ``AESFuncs`` handlers, 5 ``ClearFuncs`` handlers, and
``AuthFuncs._auth_impl`` were converted from sync-blocking to ``async def``
on the master worker's event loop.  The existing unit tests are heavy on
mocks and only prove the plumbing calls the mocks — they do NOT prove:

* multiple concurrent AES requests actually run in parallel on a single
  MWorker,
* the loop stays responsive while handlers are in flight,
* the real pillar / returner / fileserver / RSA-verify subsystems still
  return correct results under the async path.

Approach
--------
Spinning full salt daemons (master + minion) for every concurrency
scenario blows the per-test budget on CI, so we use the documented
fallback: instantiate a real ``AESFuncs`` against a per-test tmp
``pki``/``pillar_roots``/``file_roots`` tree, attach it to an
``MWorker`` skeleton, and drive ``_handle_aes`` with real payloads
through ``asyncio.gather``.  Every dispatch goes through the same
``run_func`` -> ``_run_func_async`` -> ``_wrap_run_func_return`` path
the real worker uses.
"""

# pylint: skip-file
import asyncio
import collections
import logging
import pathlib
import threading
import time

import pytest

import salt.config
import salt.crypt
import salt.master
import salt.utils.files

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_worker(aes_funcs):
    """MWorker skeleton wired to a real ``AESFuncs``.

    Bypasses ``MWorker.__init__`` (which forks a process) and only sets
    the attributes ``_handle_aes`` reads. The worker's ``opts`` mirrors
    ``aes_funcs.opts`` so the request_context set on the ioloop carries
    the master's log format defaults — otherwise handlers that log via
    ``salt._logging.impl`` raise ``KeyError('log_fmt_minion_id')`` under
    the async dispatch path.
    """
    worker = salt.master.MWorker.__new__(salt.master.MWorker)
    # Take a shallow copy and force master_stats off so we skip the
    # ``_post_stats`` codepath which depends on ``self.aes_funcs.event``.
    worker.opts = dict(aes_funcs.opts)
    worker.opts["master_stats"] = False
    worker.aes_funcs = aes_funcs
    worker.stats = collections.defaultdict(lambda: {"mean": 0, "runs": 0})
    return worker


def _base_opts(tmp_path):
    """Full ``AESFuncs`` opts backed by ``tmp_path``.

    Uses ``salt.config.master_config(None)`` so every default (of which
    the fileserver/pillar backends read many) is populated; only the
    per-test paths and a few knobs are overridden.
    """
    pki_dir = tmp_path / "pki"
    pki_dir.mkdir()
    (pki_dir / "minions").mkdir()
    (pki_dir / "minions_pre").mkdir()
    (pki_dir / "minions_rejected").mkdir()
    (pki_dir / "minions_denied").mkdir()
    (tmp_path / "cache").mkdir()
    (tmp_path / "sock_drawer").mkdir()
    opts = salt.config.master_config(None)
    opts["__role"] = "master"
    opts["pki_dir"] = str(pki_dir)
    opts["cachedir"] = str(tmp_path / "cache")
    opts["sock_dir"] = str(tmp_path / "sock_drawer")
    opts["conf_file"] = str(tmp_path / "config.conf")
    opts["fileserver_backend"] = ["roots"]
    opts["master_job_cache"] = "local_cache"
    opts["job_cache"] = True
    opts["ext_job_cache"] = ""
    opts["keys.cache_driver"] = "localfs_key"
    opts["optimization_order"] = [0, 1, 2]
    opts["master_sign_key_name"] = "master_sign"
    opts["id"] = "master"
    opts["pillar_version"] = 2
    opts["minion_data_cache"] = False
    opts["minion_data_cache_events"] = False
    opts["require_minion_sign_messages"] = False
    opts["drop_messages_signature_fail"] = False
    opts["signing_algorithm"] = salt.crypt.PKCS1v15_SHA224
    opts["encryption_algorithm"] = salt.crypt.OAEP_SHA224
    # These tests exercise the async MWorker handlers; opt in explicitly.
    # The LTS default (``master_async_mworker: False``) shadows every
    # async handler with a sync body, which breaks tests written against
    # the async signatures.
    opts["master_async_mworker"] = True
    return opts


@pytest.fixture
def minion_keypair(tmp_path):
    """Generate a real minion RSA keypair; register the pub with the master."""
    priv_pem, pub_pem = salt.crypt.gen_keys(2048)
    minion_priv = tmp_path / "minion.pem"
    minion_pub = tmp_path / "minion.pub"
    with salt.utils.files.fopen(minion_priv, "wb") as fh:
        fh.write(priv_pem if isinstance(priv_pem, bytes) else priv_pem.encode())
    with salt.utils.files.fopen(minion_pub, "wb") as fh:
        fh.write(pub_pem if isinstance(pub_pem, bytes) else pub_pem.encode())
    return {"priv_pem": priv_pem, "pub_pem": pub_pem, "priv_path": str(minion_priv)}


# ---------------------------------------------------------------------------
# 1. Concurrency: N requests through _handle_aes must run in parallel
# ---------------------------------------------------------------------------


async def test_concurrent_file_list_dispatches_in_parallel(tmp_path):
    """N ``_file_list`` dispatches with a measurable per-call latency
    finish in wall-time far less than ``N * per_call_latency``.

    ``_file_list`` offloads the sync ``Fileserver.file_list`` call to the
    default executor. To make the concurrency win observable at test
    scale we monkey-patch the fileserver's ``file_list`` to sleep briefly
    per call — real disk work at test scale is orders of magnitude
    faster than asyncio scheduling jitter, so it can't distinguish
    parallel from serial execution. The sleep exercises the same async
    dispatch path (``_handle_aes`` -> ``run_func`` ->
    ``_run_func_async`` -> ``run_in_executor``) as production.
    """
    file_roots = tmp_path / "srv" / "salt"
    file_roots.mkdir(parents=True)

    opts = _base_opts(tmp_path)
    opts["file_roots"] = {"base": [str(file_roots)]}
    aes_funcs = salt.master.AESFuncs(opts)
    try:
        worker = _make_worker(aes_funcs)

        per_call_sleep = 0.2

        # Return per-call results tagged with the load's saltenv so the
        # test can prove no cross-contamination.
        def _sleepy_file_list(load):
            time.sleep(per_call_sleep)
            return [f"{load['saltenv']}-hello.sls"]

        aes_funcs.fs_.file_list = _sleepy_file_list

        n = 20
        payloads = [{"cmd": "_file_list", "saltenv": f"env-{i:02d}"} for i in range(n)]
        t0 = time.perf_counter()
        results = await asyncio.gather(*(worker._handle_aes(p) for p in payloads))
        elapsed = time.perf_counter() - t0
        serial_floor = n * per_call_sleep
        log.info(
            "Concurrent %d _file_list wall-time: %.2fs vs serial floor %.2fs",
            n,
            elapsed,
            serial_floor,
        )

        # Every response returned the list for its own saltenv (no cross-
        # contamination via the shared executor).
        assert len(results) == n
        for i, (ret, envelope) in enumerate(results):
            assert envelope == {"fun": "send"}
            assert ret == [f"env-{i:02d}-hello.sls"], (
                f"payload {i} got wrong result {ret!r} — concurrent "
                "handlers appear to have crossed streams."
            )

        # Concurrency proof: with N=20 sleepy calls and the default
        # ThreadPoolExecutor (min ~8 workers on py 3.10), wall-time must
        # be well under half of the serialized floor. Being conservative
        # (0.5) to absorb GHA CI jitter.
        assert elapsed < serial_floor * 0.5, (
            f"Concurrent dispatch took {elapsed:.2f}s but serial floor is "
            f"{serial_floor:.2f}s — handlers appear to be running "
            "sequentially, not in parallel via the executor."
        )
    finally:
        aes_funcs.destroy()


async def test_fast_handler_stays_responsive_under_load(tmp_path):
    """A fast handler queued behind N slow blocking handlers must complete
    promptly — the executor keeps the ioloop unblocked.

    We monkey-patch the fileserver call to sleep, saturate the executor
    with concurrent slow calls, then dispatch one fast handler
    (``_master_opts``) and assert its wall-time stays well below the slow
    call latency.  If the migration accidentally serialized handlers on
    the ioloop this fast call would queue behind every slow one.
    """
    file_roots = tmp_path / "srv" / "salt"
    file_roots.mkdir(parents=True)
    opts = _base_opts(tmp_path)
    opts["file_roots"] = {"base": [str(file_roots)]}
    aes_funcs = salt.master.AESFuncs(opts)
    try:
        worker = _make_worker(aes_funcs)

        slow_sleep = 0.5

        def _slow_file_list(load):
            time.sleep(slow_sleep)
            return ["slow-result"]

        # Replace only the sync body; the async wrapper still offloads via
        # ``run_in_executor`` so this is a realistic test of loop
        # responsiveness under handler load.
        aes_funcs.fs_.file_list = _slow_file_list

        # Fire 8 slow calls concurrently; they saturate the default
        # executor's worker pool (min 8 for asyncio's default).
        slow_tasks = [
            asyncio.create_task(
                worker._handle_aes({"cmd": "_file_list", "saltenv": "base"})
            )
            for _ in range(8)
        ]

        # Give the slow tasks a moment to actually enter the executor.
        await asyncio.sleep(0.05)

        # Dispatch a fast handler (`_master_opts` -> `_file_envs` offload,
        # which is also async but returns almost immediately with an empty
        # roots tree). Measure only its response time.
        t0 = time.perf_counter()
        ret, envelope = await worker._handle_aes(
            {"cmd": "_master_opts", "id": "quick-minion", "env_only": True}
        )
        fast_elapsed = time.perf_counter() - t0
        log.info(
            "Fast _master_opts under load: %.3fs (slow_sleep=%.2fs)",
            fast_elapsed,
            slow_sleep,
        )

        # Loop stayed responsive: fast handler completed well before the
        # slow calls' sleep.
        assert fast_elapsed < slow_sleep, (
            f"Fast handler took {fast_elapsed:.3f}s — longer than a single "
            f"slow call ({slow_sleep}s). The ioloop appears to be blocked "
            "by concurrent slow handlers."
        )
        assert envelope == {"fun": "send"}
        assert isinstance(ret, dict)

        # Let the slow tasks finish so the test tears down cleanly.
        await asyncio.gather(*slow_tasks)
    finally:
        aes_funcs.destroy()


# ---------------------------------------------------------------------------
# 2. Real subsystems exercised concurrently
# ---------------------------------------------------------------------------


async def test_concurrent_pillar_renders_return_correct_data_per_minion(tmp_path):
    """N ``_pillar`` requests each with a distinct minion id must each get
    back the pillar tree that matches their id — the async rewrite must
    not cross-contaminate results across concurrent awaits.

    Uses a real ``AsyncPillar`` render (no mocks): a jinja pillar top +
    per-minion sls that emits ``{'minion_id': <id>}``.  If two concurrent
    renders swap loads, the assertion fires.
    """
    pillar_roots = tmp_path / "pillar"
    pillar_roots.mkdir()
    # Top file matches every minion; per-minion pillar is a jinja file that
    # reads grains['id'] and echoes it into the pillar tree.
    (pillar_roots / "top.sls").write_text("base:\n" "  '*':\n" "    - identity\n")
    (pillar_roots / "identity.sls").write_text(
        "minion_id: {{ grains['id'] }}\n" "static_key: static_value\n"
    )

    opts = _base_opts(tmp_path)
    opts["pillar_roots"] = {"base": [str(pillar_roots)]}
    opts["file_roots"] = {"base": [str(tmp_path / "empty_roots")]}
    (tmp_path / "empty_roots").mkdir()
    opts["file_client"] = "local"
    opts["state_top"] = "top.sls"
    opts["state_top_saltenv"] = None
    opts["nodegroups"] = {}
    opts["renderer"] = "jinja|yaml"
    opts["renderer_blacklist"] = []
    opts["renderer_whitelist"] = []
    opts["ext_pillar"] = []
    opts["on_demand_ext_pillar"] = []
    opts["pillar_cache"] = False
    opts["pillar_source_merging_strategy"] = "smart"
    opts["pillar_merge_lists"] = False
    opts["pillarenv"] = None
    opts["pillarenv_from_saltenv"] = False
    opts["pillar_raise_on_missing"] = False
    opts["decrypt_pillar"] = []
    opts["decrypt_pillar_default"] = "gpg"
    opts["decrypt_pillar_delimiter"] = ":"
    opts["decrypt_pillar_renderers"] = ["gpg"]
    opts["saltenv"] = None
    opts["default_top"] = "base"
    opts["top_file_merging_strategy"] = "merge"
    opts["env_order"] = []

    aes_funcs = salt.master.AESFuncs(opts)
    try:
        worker = _make_worker(aes_funcs)

        # 6 distinct minion ids; run all concurrently through _handle_aes.
        minion_ids = [f"minion-{i:02d}" for i in range(6)]
        payloads = [
            {
                "cmd": "_pillar",
                "id": mid,
                "grains": {"os": "Debian", "id": mid},
                "saltenv": "base",
                "ver": "2",
            }
            for mid in minion_ids
        ]
        results = await asyncio.gather(*(worker._handle_aes(p) for p in payloads))

        for mid, (data, envelope) in zip(minion_ids, results):
            assert envelope == {
                "fun": "send_private",
                "key": "pillar",
                "tgt": mid,
            }, mid
            # The pillar render for THIS minion must produce THIS minion's
            # id — otherwise concurrent renders crossed streams.
            assert (
                data.get("minion_id") == mid
            ), f"Pillar for {mid} returned wrong minion_id: {data!r}"
            assert data.get("static_key") == "static_value", mid
    finally:
        aes_funcs.destroy()


async def test_concurrent_return_writes_all_jobs_to_local_cache(tmp_path):
    """N distinct ``_return`` payloads (jid+id unique per request) all end
    up on disk via the real ``local_cache`` returner.

    ``_return`` offloads ``salt.utils.job.store_job`` to the executor;
    this test proves the offloaded writes don't clobber each other under
    concurrency and every payload's jid is persisted.
    """
    opts = _base_opts(tmp_path)
    (tmp_path / "empty_roots").mkdir()
    opts["file_roots"] = {"base": [str(tmp_path / "empty_roots")]}
    opts["master_job_cache"] = "local_cache"
    opts["job_cache"] = True
    opts["keep_jobs_seconds"] = 3600

    aes_funcs = salt.master.AESFuncs(opts)
    try:
        worker = _make_worker(aes_funcs)

        n = 20
        base_jid = int(time.time() * 1000000)
        jids = [str(base_jid + i) for i in range(n)]
        payloads = [
            {
                "cmd": "_return",
                "id": f"minion-{i:02d}",
                "jid": jid,
                "fun": "test.ping",
                "fun_args": [],
                "return": True,
                "retcode": 0,
                "success": True,
                "out": "nested",
            }
            for i, jid in enumerate(jids)
        ]
        # ``_return``'s envelope is ``(None, {"fun": "send"})`` — we don't
        # check payload equality, only that every dispatch completes.
        results = await asyncio.gather(*(worker._handle_aes(p) for p in payloads))
        for _, envelope in results:
            assert envelope == {"fun": "send"}

        # Real returner disk verification: local_cache stores returns
        # under ``cachedir/jobs/<hash-prefix>/<jid>/<minion_id>/return.p``.
        # Confirm every dispatched (jid, minion_id) pair is recoverable
        # via ``local_cache.get_jid`` — proves the concurrent async
        # offload of ``store_job`` didn't drop any writes.
        import salt.returners.local_cache as local_cache

        # ``local_cache`` is a returner: loader normally injects
        # ``__opts__`` into the module namespace. Bypass the loader by
        # setting it directly so we can call the module functions from a
        # test.
        local_cache.__opts__ = opts

        for i, jid in enumerate(jids):
            entry = local_cache.get_jid(jid)
            assert entry, (
                f"jid {jid} (minion-{i:02d}) missing from local_cache — "
                "async offload of store_job dropped a concurrent write."
            )
            key = f"minion-{i:02d}"
            assert (
                key in entry
            ), f"jid {jid} present but missing minion key {key!r}: {entry!r}"
            assert entry[key]["return"] is True
            assert entry[key]["success"] is True
    finally:
        aes_funcs.destroy()


async def test_verify_minion_concurrent_real_rsa(tmp_path, minion_keypair):
    """Real RSA verify_minion under concurrent load.

    Register the minion's pub key with the master, then run 30 concurrent
    ``verify_minion`` calls through ``_handle_aes`` — each call must
    return ``True`` (correct signature) and no calls must cross-verify
    against a different minion's token.
    """
    opts = _base_opts(tmp_path)
    (tmp_path / "empty_roots").mkdir()
    opts["file_roots"] = {"base": [str(tmp_path / "empty_roots")]}

    # Register two minion keys and cross-check that each verifies only
    # against its own token (catches cross-contamination under concurrent
    # RSA offload).
    priv2, pub2 = salt.crypt.gen_keys(2048)
    minion_a_id = "minion-alpha"
    minion_b_id = "minion-bravo"

    aes_funcs = salt.master.AESFuncs(opts)
    try:
        # Store both pub keys in the master's PKI ``accepted`` bucket.
        # ``localfs_key.store`` demands ``data={'pub': pem, 'state':
        # 'accepted'}`` and routes to ``<pki_dir>/minions/<id>``.
        aes_funcs.key_cache.store(
            "keys",
            minion_a_id,
            {"pub": minion_keypair["pub_pem"], "state": "accepted"},
        )
        aes_funcs.key_cache.store(
            "keys",
            minion_b_id,
            {
                "pub": pub2 if isinstance(pub2, str) else pub2.decode(),
                "state": "accepted",
            },
        )

        # Build the signed tokens each minion would send in an AES
        # authenticated request. ``verify_minion`` expects the token to
        # decrypt to b"salt".
        priv_a = salt.crypt.PrivateKey.from_str(minion_keypair["priv_pem"])
        priv_b = salt.crypt.PrivateKey.from_str(priv2)
        token_a = priv_a.encrypt(b"salt")
        token_b = priv_b.encrypt(b"salt")

        worker = _make_worker(aes_funcs)

        # Fire 30 concurrent verify_minion calls, alternating between the
        # two minions. Each should return True.
        n = 30
        payloads = []
        expected_ids = []
        for i in range(n):
            if i % 2 == 0:
                payloads.append((minion_a_id, token_a))
                expected_ids.append(minion_a_id)
            else:
                payloads.append((minion_b_id, token_b))
                expected_ids.append(minion_b_id)

        # ``verify_minion`` is called by ``_handle_aes``? No — it's exposed
        # on ``AESFuncs`` but has a 2-arg signature and is invoked directly
        # by the channel server, not via a load-dict cmd dispatch. Test it
        # by awaiting through ``AESFuncs`` (the async offload path is the
        # code we care about) and confirm concurrency doesn't corrupt
        # results.
        t0 = time.perf_counter()
        results = await asyncio.gather(
            *(aes_funcs.verify_minion(mid, tok) for mid, tok in payloads)
        )
        elapsed = time.perf_counter() - t0
        log.info(
            "%d concurrent verify_minion (real RSA) wall-time: %.3fs",
            n,
            elapsed,
        )

        # All must verify True — no cross-contamination.
        assert all(
            r is True for r in results
        ), f"Some verify_minion calls returned False: {results}"

        # Bonus: verify the negative path is honoured under concurrency —
        # A signed with A's key but claiming to be B must fail.
        cross_result = await aes_funcs.verify_minion(minion_b_id, token_a)
        assert cross_result is False, (
            "Cross-key verify_minion returned True; concurrent RSA offload "
            "may have leaked key state across calls."
        )
    finally:
        aes_funcs.destroy()


# ---------------------------------------------------------------------------
# 3. Correctness under concurrency: heterogeneous handlers
# ---------------------------------------------------------------------------


async def test_mixed_handler_workload_returns_correct_envelopes(tmp_path):
    """Concurrently dispatch a mix of ``_file_list``, ``_master_opts``, and
    ``_return`` and confirm every response's envelope matches its cmd.

    Regression guard for the ``_wrap_run_func_return`` post-processing
    that lives inside the async dispatch path — a bug there could send
    ``_return``'s ``{'fun': 'send'}`` envelope to another handler.
    """
    file_roots = tmp_path / "srv" / "salt"
    file_roots.mkdir(parents=True)
    (file_roots / "hello.sls").write_text("# hello\n")

    opts = _base_opts(tmp_path)
    opts["file_roots"] = {"base": [str(file_roots)]}
    opts["master_job_cache"] = "local_cache"
    opts["job_cache"] = True
    # ``roots.py`` lazily creates ``<cachedir>/file_lists/roots`` on the
    # first call; concurrent callers race the ``os.makedirs`` and the
    # losers log CRITICAL + return []. Pre-create it so the test measures
    # dispatch correctness, not that filesystem race.
    (pathlib.Path(opts["cachedir"]) / "file_lists" / "roots").mkdir(
        parents=True, exist_ok=True
    )

    aes_funcs = salt.master.AESFuncs(opts)
    try:
        worker = _make_worker(aes_funcs)

        payloads = []
        base_jid = int(time.time() * 1000000)
        for i in range(6):
            payloads.append(("_file_list", {"cmd": "_file_list", "saltenv": "base"}))
            payloads.append(
                (
                    "_master_opts",
                    {"cmd": "_master_opts", "id": "minion-x", "env_only": True},
                )
            )
            payloads.append(
                (
                    "_return",
                    {
                        "cmd": "_return",
                        "id": f"minion-{i:02d}",
                        "jid": str(base_jid + i),
                        "fun": "test.ping",
                        "return": True,
                        "retcode": 0,
                        "success": True,
                    },
                )
            )

        results = await asyncio.gather(
            *(worker._handle_aes(load) for _, load in payloads)
        )

        expected_envelope = {"fun": "send"}
        for (cmd, _), (ret, envelope) in zip(payloads, results):
            assert (
                envelope == expected_envelope
            ), f"cmd {cmd} got wrong envelope {envelope!r}"
            if cmd == "_file_list":
                assert isinstance(ret, list) and "hello.sls" in ret
            elif cmd == "_master_opts":
                assert isinstance(ret, dict) and "file_roots" in ret
            # _return returns None -> envelope only, no ret assertion.
    finally:
        aes_funcs.destroy()


# ---------------------------------------------------------------------------
# 4. master_mworker_max_inflight cap — end-to-end through _handle_payload
# ---------------------------------------------------------------------------


def _inflight_worker(aes_funcs):
    """MWorker skeleton wired for ``_handle_payload`` (not ``_handle_aes``).

    ``_handle_payload`` needs both ``_modules_loaded`` and
    ``aes_funcs`` / ``clear_funcs`` attributes, plus a ``req_channels``
    stub for ``_handle_signals``.  Bypass ``__init__`` because that
    forks and we only want the coroutine's dispatch path.
    """
    worker = salt.master.MWorker.__new__(salt.master.MWorker)
    worker.opts = dict(aes_funcs.opts)
    worker.opts["master_stats"] = False
    worker.aes_funcs = aes_funcs
    # Minimal ClearFuncs stub; the cap tests only fire AES payloads so
    # ``_handle_clear`` is never entered.  Keep attribute presence so
    # the guard in ``_handle_payload_inner`` doesn't short-circuit.
    worker.clear_funcs = object()
    worker.stats = collections.defaultdict(lambda: {"mean": 0, "runs": 0})
    worker._modules_loaded = threading.Event()
    worker._modules_loaded.set()
    return worker


async def test_max_inflight_cap_bounds_concurrent_returns(tmp_path):
    """
    With ``master_mworker_max_inflight = 3`` and 12 concurrent
    ``_return`` dispatches — each patched to sleep 0.2 s — the number of
    handlers executing at any instant MUST NEVER exceed 3, and the
    total wall time MUST be at least ceil(12/3) * 0.2 = 0.8 s.
    """
    file_roots = tmp_path / "srv" / "salt"
    file_roots.mkdir(parents=True)
    opts = _base_opts(tmp_path)
    opts["file_roots"] = {"base": [str(file_roots)]}
    opts["master_mworker_max_inflight"] = 3
    aes_funcs = salt.master.AESFuncs(opts)
    try:
        worker = _inflight_worker(aes_funcs)
        # Reset the module-level counters so a prior test's residuals
        # don't leak in.
        salt.master._MW_INFLIGHT["waiters"] = 0
        base_wait_ms = salt.master._MW_INFLIGHT["wait_ms_total"]

        per_call_sleep = 0.2

        active = 0
        max_active = 0
        active_lock = asyncio.Lock()

        async def _fake_return(load):
            nonlocal active, max_active
            async with active_lock:
                active += 1
                if active > max_active:
                    max_active = active
            try:
                await asyncio.sleep(per_call_sleep)
                return None
            finally:
                async with active_lock:
                    active -= 1

        aes_funcs._return = _fake_return  # type: ignore[assignment]

        n = 12
        cap = 3
        payloads = [
            {
                "enc": "aes",
                "load": {
                    "cmd": "_return",
                    "id": f"minion-{i:02d}",
                    "jid": str(20260825000000 + i),
                    "return": True,
                },
            }
            for i in range(n)
        ]

        t0 = time.perf_counter()
        results = await asyncio.gather(*(worker._handle_payload(p) for p in payloads))
        elapsed = time.perf_counter() - t0

        assert len(results) == n
        assert max_active <= cap, (
            f"cap violated: observed {max_active} concurrent handlers, "
            f"expected at most {cap}"
        )
        # ceil(n/cap) waves of per_call_sleep, minus one scheduling
        # tick.  Being conservative (0.75x) to absorb CI jitter.
        expected_floor = (n // cap + (0 if n % cap == 0 else 1)) * per_call_sleep
        assert elapsed >= expected_floor * 0.75, (
            f"wall time {elapsed:.2f}s is below the {expected_floor:.2f}s "
            f"floor — cap does not appear to be gating concurrency"
        )

        # The waiter gauge drained back to zero and the accumulator
        # counted some wait time (some tasks queued behind the cap).
        assert salt.master._MW_INFLIGHT["waiters"] == 0
        assert salt.master._MW_INFLIGHT["wait_ms_total"] >= base_wait_ms
        # At least one request had to wait — with n=12, cap=3, sleep
        # 0.2s the tail requests wait ~0.6s cumulatively across the
        # pool.  Assert a very loose lower bound to avoid CI flakes.
        assert (
            salt.master._MW_INFLIGHT["wait_ms_total"] - base_wait_ms
        ) >= 100, "wait_ms_total did not accumulate — cap not exercised"
    finally:
        aes_funcs.destroy()


async def test_max_inflight_cap_zero_allows_full_concurrency(tmp_path):
    """
    Regression: ``master_mworker_max_inflight = 0`` MUST leave the
    dispatch path unthrottled — 8 concurrent ``_return`` handlers all
    run in parallel and wall time approaches the single-call floor
    (0.2 s), not the serialized 1.6 s floor.
    """
    file_roots = tmp_path / "srv" / "salt"
    file_roots.mkdir(parents=True)
    opts = _base_opts(tmp_path)
    opts["file_roots"] = {"base": [str(file_roots)]}
    opts["master_mworker_max_inflight"] = 0
    aes_funcs = salt.master.AESFuncs(opts)
    try:
        worker = _inflight_worker(aes_funcs)

        per_call_sleep = 0.2
        active = 0
        max_active = 0
        active_lock = asyncio.Lock()

        async def _fake_return(load):
            nonlocal active, max_active
            async with active_lock:
                active += 1
                if active > max_active:
                    max_active = active
            try:
                await asyncio.sleep(per_call_sleep)
                return None
            finally:
                async with active_lock:
                    active -= 1

        aes_funcs._return = _fake_return  # type: ignore[assignment]

        n = 8
        payloads = [
            {
                "enc": "aes",
                "load": {
                    "cmd": "_return",
                    "id": f"minion-{i:02d}",
                    "jid": str(20260825100000 + i),
                    "return": True,
                },
            }
            for i in range(n)
        ]
        t0 = time.perf_counter()
        await asyncio.gather(*(worker._handle_payload(p) for p in payloads))
        elapsed = time.perf_counter() - t0

        assert max_active == n, (
            f"cap-zero (unlimited) broke: only {max_active} of {n} "
            "handlers ran concurrently"
        )
        # Wall time is dominated by a single per_call_sleep + scheduling
        # overhead.  Be generous (2x) to absorb CI jitter.
        assert elapsed < per_call_sleep * 2, (
            f"cap-zero wall time {elapsed:.2f}s exceeded {per_call_sleep * 2:.2f}s "
            "— dispatches appear to be serialized despite cap=0"
        )
        # Semaphore MUST NOT have been built.
        assert worker._inflight_sem is None
    finally:
        aes_funcs.destroy()


async def test_max_inflight_cap_flag_off_is_noop(tmp_path):
    """
    With ``master_async_mworker = False`` the cap MUST be a no-op even
    when set to a positive integer — sync dispatch naturally tops out
    at 1 in flight, so a semaphore would just add overhead / mask the
    LTS fast path.  The semaphore MUST NOT be built.
    """
    file_roots = tmp_path / "srv" / "salt"
    file_roots.mkdir(parents=True)
    opts = _base_opts(tmp_path)
    opts["file_roots"] = {"base": [str(file_roots)]}
    # Force the "async off, cap set" combination that a nervous
    # operator might reach for.
    opts["master_async_mworker"] = False
    opts["master_mworker_max_inflight"] = 2

    # The base opts fixture flipped ``master_async_mworker`` back on
    # for the AESFuncs constructor to produce the async handler
    # signatures the rest of this file relies on.  Instantiate
    # AESFuncs with the async flag still set, then rebuild the worker
    # with the async flag off so we're testing the correct path.
    opts_for_funcs = dict(opts)
    opts_for_funcs["master_async_mworker"] = True
    aes_funcs = salt.master.AESFuncs(opts_for_funcs)
    try:
        worker = _inflight_worker(aes_funcs)
        worker.opts["master_async_mworker"] = False
        worker.opts["master_mworker_max_inflight"] = 2

        async def _fake_return(load):
            await asyncio.sleep(0.01)
            return None

        aes_funcs._return = _fake_return  # type: ignore[assignment]

        await worker._handle_payload(
            {
                "enc": "aes",
                "load": {
                    "cmd": "_return",
                    "id": "minion",
                    "jid": "1",
                    "return": True,
                },
            }
        )
        assert worker._inflight_sem is None
        assert worker._inflight_sem_ready is True
    finally:
        aes_funcs.destroy()
