import asyncio
import contextlib
import logging
import os
import re

import pytest

import salt.config
import salt.transport.tcp
from tests.conftest import FIPS_TESTRUN
from tests.support.mock import AsyncMock, MagicMock, patch
from tests.support.runtests import RUNTIME_VARS


# ----------------------------------------------------------------------
# ``RUNTIME_VARS.TMP`` (``/tmp/salt-tests-tmpdir-<uid>``) is used by a
# handful of unit tests (e.g. ``test_pillar.test_topfile_order``) as a
# parent for ``tempfile.mkdtemp(dir=...)``. Nothing in the pure-unit
# session guarantees the directory exists — the integration-side
# ``saltfactories`` fixtures normally create it, but they are not pulled
# in for a bare unit run. Under CI parallelism the parent can also be
# cleaned between tests. Create it eagerly at session start so unit
# tests can rely on it without each test carrying its own ``makedirs``.
# ----------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _ensure_runtime_vars_tmp_exists():
    os.makedirs(RUNTIME_VARS.TMP, exist_ok=True)
    yield


# ----------------------------------------------------------------------
# asyncio blocking-detection fixture (see MEMORY: async-mworker migration)
# ----------------------------------------------------------------------
#
# The MWorker migration converts ``AESFuncs``/``ClearFuncs``/``AuthFuncs``
# handlers to ``async def``. Any handler that accidentally holds the event
# loop (sync ``open()``, RSA verify without ``run_in_executor``, ``time.sleep``,
# etc.) defeats the migration silently unless something in the test suite
# catches it. This module wires asyncio's built-in slow-callback logging
# into a pytest fixture that FAILS the test when a callback exceeds the
# configured threshold.
#
# The fixture is opt-out via ``@pytest.mark.no_blocking``. Use the marker
# on tests that do legitimate synchronous CPU work (e.g. RSA keypair
# generation inside a callback for a security assertion).
#
# Threshold is 50 ms by default (matches the migration's design budget).
# Override per-test with ``@pytest.mark.no_blocking(threshold=0.1)``.
# ----------------------------------------------------------------------

# Default slow-callback threshold, in seconds. 50 ms is the design budget
# for MWorker handlers — anything longer should have been offloaded to a
# thread/process pool via ``loop.run_in_executor``.
DEFAULT_SLOW_CALLBACK_THRESHOLD = 0.05

# asyncio logs two shapes of slow warnings when ``loop._debug`` is True:
#   1. "Executing <Handle func at ...> took X seconds" — a single callback
#      held the loop for >slow_callback_duration. This is the "handler
#      blocked the loop" signal we care about.
#   2. "Executing <Task pending name='Task-N' coro=<...>> took X seconds"
#      — a whole Task ran for X seconds between yields. This fires for
#      any legitimate long-running test coroutine (heavy AsyncMock setup,
#      real I/O between awaits) and is NOT a handler bug — the loop was
#      not blocked, the Task simply took a while to complete overall.
# Match only the Handle shape so tests can legitimately do 100+ ms of
# awaited work without tripping.
_SLOW_CALLBACK_RE = re.compile(r"\bExecuting <Handle\b.*\btook\b.*\bseconds\b")


class _SlowCallbackCollector(logging.Handler):
    """Capture asyncio slow-callback warnings for later assertion."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.records = []

    def emit(self, record):
        try:
            message = record.getMessage()
        except Exception:  # pylint: disable=broad-except
            return
        if _SLOW_CALLBACK_RE.search(message):
            self.records.append((record.levelno, message))


@contextlib.contextmanager
def _asyncio_blocking_detector(threshold):
    """
    Context manager: enable slow-callback detection on any loop created
    inside the block, and yield a collector that captured warnings can
    be read from.

    Because pytest fixtures run before the test's event loop is created
    by the ``io_loop`` fixture, we monkeypatch ``asyncio.new_event_loop``
    and ``asyncio.get_event_loop`` for the duration of the test so that
    the returned loop always has debug + slow_callback_duration set.
    """
    collector = _SlowCallbackCollector()
    asyncio_logger = logging.getLogger("asyncio")
    prev_level = asyncio_logger.level
    asyncio_logger.addHandler(collector)
    # ``asyncio`` logger default level is WARNING; make sure warnings
    # propagate to the handler regardless of caller config.
    if prev_level > logging.WARNING or prev_level == logging.NOTSET:
        asyncio_logger.setLevel(logging.WARNING)

    original_new_event_loop = asyncio.new_event_loop

    def _debug_new_event_loop():
        loop = original_new_event_loop()
        loop.set_debug(True)
        loop.slow_callback_duration = threshold
        return loop

    # Also patch any already-current loop so tests that reuse it get the
    # instrumentation immediately.
    try:
        current = asyncio.get_event_loop_policy().get_event_loop()
    except Exception:  # pylint: disable=broad-except
        current = None
    prev_debug = None
    prev_threshold = None
    if current is not None and not current.is_closed():
        prev_debug = current.get_debug()
        prev_threshold = getattr(
            current, "slow_callback_duration", DEFAULT_SLOW_CALLBACK_THRESHOLD
        )
        current.set_debug(True)
        current.slow_callback_duration = threshold

    asyncio.new_event_loop = _debug_new_event_loop
    try:
        yield collector
    finally:
        asyncio.new_event_loop = original_new_event_loop
        if current is not None and not current.is_closed():
            try:
                current.set_debug(prev_debug)
                current.slow_callback_duration = prev_threshold
            except Exception:  # pylint: disable=broad-except
                pass
        asyncio_logger.removeHandler(collector)
        asyncio_logger.setLevel(prev_level)


@pytest.fixture(autouse=True)
def _asyncio_blocking_detection(request):
    """
    Autouse fixture that enables asyncio slow-callback detection for
    every test in ``tests/pytests/unit`` (including subdirs).

    Opt out with ``@pytest.mark.no_blocking`` or override the threshold
    with ``@pytest.mark.no_blocking(threshold=0.1)`` /
    ``@pytest.mark.no_blocking(reason="RSA-heavy fixture setup")``.

    ``PYTHONASYNCIODEBUG=1`` cannot be set retroactively because Python
    consults it only at ``asyncio.new_event_loop()`` time; we achieve the
    same effect by calling ``loop.set_debug(True)`` inside the fixture.
    """
    marker = request.node.get_closest_marker("no_blocking")
    if marker is not None:
        threshold_kw = marker.kwargs.get("threshold")
        if threshold_kw is None:
            # Marker without threshold override == disable detection.
            yield
            return
        threshold = float(threshold_kw)
    else:
        threshold = DEFAULT_SLOW_CALLBACK_THRESHOLD

    with _asyncio_blocking_detector(threshold) as collector:
        yield
        if collector.records:
            joined = "\n".join(
                f"  [{logging.getLevelName(lvl)}] {msg}"
                for lvl, msg in collector.records
            )
            pytest.fail(
                "asyncio slow-callback threshold of %.3fs exceeded during test "
                "'%s' (%d violation(s)):\n%s\n"
                "Fix the handler (offload sync work with "
                "loop.run_in_executor) or exempt with "
                "@pytest.mark.no_blocking."
                % (threshold, request.node.name, len(collector.records), joined)
            )


def pytest_configure(config):
    """Register the ``no_blocking`` marker for this test package."""
    config.addinivalue_line(
        "markers",
        "no_blocking(threshold=None, reason=None): Disable the asyncio "
        "blocking-detection fixture for this test, or raise the "
        "slow-callback threshold to ``threshold`` seconds.",
    )


# Tests that instantiate ``salt.master.AESFuncs(opts)`` inline (heavy loader
# init + a background ``_TCPPubServerPublisher._connect`` task that waits ~1s
# for its socket) share one event-loop callback slice with the handler under
# test. The blocking-detection fixture cannot distinguish handler-owned CPU
# from test-fixture setup here; mark them exempt centrally so the individual
# test bodies stay uncluttered. Refactoring the setup into a session fixture
# (so AESFuncs is built outside the loop) would let us drop these entries.
_NO_BLOCKING_TEST_PREFIXES = ("test_register_resources_",)


def pytest_collection_modifyitems(config, items):  # pylint: disable=unused-argument
    """Auto-apply ``no_blocking`` to tests with known heavy inline setup."""
    for item in items:
        if any(item.name.startswith(p) for p in _NO_BLOCKING_TEST_PREFIXES):
            if item.get_closest_marker("no_blocking") is None:
                item.add_marker(
                    pytest.mark.no_blocking(
                        reason="Heavy AESFuncs() init runs inline; see "
                        "conftest _NO_BLOCKING_TEST_PREFIXES for details."
                    )
                )


@pytest.fixture
def minion_opts(tmp_path):
    """
    Default minion configuration with relative temporary paths to not require root permissions.
    """
    root_dir = tmp_path / "minion"
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["__role"] = "minion"
    opts["root_dir"] = str(root_dir)
    opts["master_uri"] = "tcp://{ip}:{port}".format(
        ip="127.0.0.1", port=opts["master_port"]
    )
    for name in ("cachedir", "pki_dir", "sock_dir", "conf_dir"):
        dirpath = root_dir / name
        dirpath.mkdir(parents=True)
        opts[name] = str(dirpath)
    opts["log_file"] = "logs/minion.log"
    opts["conf_file"] = os.path.join(opts["conf_dir"], "minion")
    opts["fips_mode"] = FIPS_TESTRUN
    opts["encryption_algorithm"] = "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"
    opts["signing_algorithm"] = "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
    opts["lazy_loader_strict_matching"] = True
    return opts


@pytest.fixture
def master_opts(tmp_path):
    """
    Default master configuration with relative temporary paths to not require root permissions.
    """
    root_dir = tmp_path / "master"
    opts = salt.config.master_config(None)
    opts["__role"] = "master"
    opts["root_dir"] = str(root_dir)
    for name in ("cachedir", "pki_dir", "sock_dir", "conf_dir"):
        dirpath = root_dir / name
        dirpath.mkdir(parents=True)
        opts[name] = str(dirpath)
    opts["log_file"] = "logs/master.log"
    opts["conf_file"] = os.path.join(opts["conf_dir"], "master")
    opts["fips_mode"] = FIPS_TESTRUN
    opts["publish_signing_algorithm"] = (
        "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
    )
    # The unit test suite exercises the async MWorker dispatch path
    # extensively (``await aes_funcs._pillar(...)`` etc.).  The LTS
    # default (``master_async_mworker: False``) shadows those handlers
    # with sync bodies, which would break every ``await`` in the suite.
    # Opt in explicitly for tests; the OFF path is covered by
    # ``test_master_async_optin.py``.
    opts["master_async_mworker"] = True

    # Use optimized worker pools for tests to demonstrate the feature
    # This separates fast operations from slow ones for better performance
    opts["worker_pools_enabled"] = True
    opts["worker_pools"] = {
        "fast": {
            "worker_count": 2,
            "commands": [
                "ping",
                "get_token",
                "mk_token",
                "verify_minion",
                "_master_opts",
            ],
        },
        "general": {
            "worker_count": 3,
            "commands": ["*"],  # Catchall for everything else
        },
    }

    return opts


@pytest.fixture
def syndic_opts(tmp_path):
    """
    Default master configuration with relative temporary paths to not require root permissions.
    """
    root_dir = tmp_path / "syndic"
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["syndic_master"] = "127.0.0.1"
    opts["__role"] = "minion"
    opts["root_dir"] = str(root_dir)
    for name in ("cachedir", "pki_dir", "sock_dir", "conf_dir"):
        dirpath = root_dir / name
        dirpath.mkdir(parents=True)
        opts[name] = str(dirpath)
    opts["log_file"] = "logs/syndic.log"
    opts["conf_file"] = os.path.join(opts["conf_dir"], "syndic")
    return opts


@pytest.fixture
def mocked_tcp_pub_client():
    # Use AsyncMock rather than an asyncio.Future so the fixture does not
    # depend on the presence of a running/default event loop at fixture
    # setup time. Some tests in the unit suite call
    # asyncio.set_event_loop(None) during teardown which leaves
    # asyncio.get_event_loop() raising "There is no current event loop in
    # thread 'MainThread'" for the next test that uses this fixture.
    transport = MagicMock(spec=salt.transport.tcp.PublishClient)
    transport.connect = AsyncMock(return_value=True)
    with patch("salt.transport.tcp.PublishClient", transport):
        yield
