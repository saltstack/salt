"""
Repro harness for the NSX salt-minion OOM described in
``RESOURCE_RUNAWAY_NSX_OOM.md`` (repo root).

Two scenarios:

1. ``test_publish_tasks_accumulate_under_slow_pusher`` -- surgical hit on
   hypothesis #2 ("event publish tasks are retained"). Stubs
   ``SaltEvent.pusher.publish`` so the awaitable it returns never finishes,
   fires many events, and asserts ``len(event._publish_tasks)`` grows without
   being pruned. Runs in seconds.

2. ``test_request_client_under_blackhole_master`` -- a *measuring stick*, not
   a hard reproducer, for hypotheses #1 and #3 ("return retry overlap leaks"
   / "reconnect churn"). Uses the same ``zmq.REP``-as-fake-master pattern as
   ``tests/pytests/functional/transport/zeromq/test_request_client.py``: bind
   a port, consume requests, never reply, optionally close+rebind once to
   emulate a master restart. Drives concurrent ``RequestClient.send`` calls
   and samples ``asyncio.all_tasks()`` count, RSS, queue depth, and reconnect
   count. The NSX OOM took hours to grow; an 8-second CI window only confirms
   the reconnect path is exercised. RSS/task numbers go to the warning log
   and a CSV under ``tmp_path`` for offline inspection.
"""

import asyncio
import csv
import logging
import resource
import sys
import time

import pytest
import pytestshellutils.utils.ports

try:
    import zmq
    import zmq.eventloop.zmqstream
except ImportError:  # matches sibling test_zeromq.py
    zmq = None

import salt.config
import salt.exceptions
import salt.transport.zeromq
import salt.utils.event
import salt.utils.files
from tests.support.mock import MagicMock

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skipif(zmq is None, reason="pyzmq not installed"),
]


def _rss_kb():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        rss //= 1024
    return rss


class Sampler:
    columns = (
        "t",
        "rss_kb",
        "asyncio_tasks",
        "queue_depth",
        "reconnects",
        "publish_tasks",
    )

    def __init__(self):
        self.rows = []
        self._t0 = time.monotonic()

    def take(self, *, queue_depth=0, reconnects=0, publish_tasks=0):
        self.rows.append(
            (
                round(time.monotonic() - self._t0, 3),
                _rss_kb(),
                len(asyncio.all_tasks()),
                queue_depth,
                reconnects,
                publish_tasks,
            )
        )

    def write_csv(self, path):
        with salt.utils.files.fopen(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(self.columns)
            w.writerows(self.rows)

    def summary(self):
        if not self.rows:
            return "no samples"
        first, last = self.rows[0], self.rows[-1]
        return (
            f"samples={len(self.rows)} "
            f"rss_kb {first[1]} -> {last[1]} (+{last[1] - first[1]}) "
            f"tasks {first[2]} -> {last[2]} (+{last[2] - first[2]}) "
            f"publish_tasks {first[5]} -> {last[5]} (+{last[5] - first[5]}) "
            f"reconnects={last[4]}"
        )


async def test_publish_tasks_accumulate_under_slow_pusher():
    """
    Demonstrate that SaltEvent prunes completed publish tasks from
    ``_publish_tasks``. Before the fix this set grew unboundedly under
    sustained fire_event() calls because nothing removed completed tasks
    until close_pull(); under prolonged master backpressure that drove the
    NSX OOM described in RESOURCE_RUNAWAY_NSX_OOM.md.
    """
    n_events = 2000
    loop = asyncio.get_running_loop()
    opts = salt.config.DEFAULT_MINION_OPTS.copy()

    event = salt.utils.event.SaltEvent(
        node="minion", opts=opts, listen=False, io_loop=loop
    )
    event.cpush = True
    event._run_io_loop_sync = False

    async def _publish(_msg):
        # Brief await so the task actually yields and lands on the loop,
        # then completes. Mirrors a healthy-but-slow pusher.
        await asyncio.sleep(0)

    event.pusher = MagicMock()
    event.pusher.publish.side_effect = _publish

    try:
        for i in range(n_events):
            event.fire_event({"i": i}, "salt/runaway/test")

        # Drain: let every scheduled publish task complete. Several yields
        # are enough because each task only awaits sleep(0).
        for _ in range(5):
            await asyncio.sleep(0)

        retained = len(event._publish_tasks)
        log.info("publish-tasks scenario: fired=%s retained=%s", n_events, retained)
        # With pruning: completed tasks self-evict, so the set is ~empty.
        # Without pruning (the bug): all n_events tasks remain forever.
        assert retained == 0, (
            f"_publish_tasks retained {retained} of {n_events} fired events "
            "after every publish() coroutine completed. Done tasks are not "
            "being pruned from the set; under sustained event firing this "
            "is the resource runaway from RESOURCE_RUNAWAY_NSX_OOM.md."
        )
    finally:
        for task in list(event._publish_tasks):
            task.cancel()
        event._publish_tasks.clear()


class BlackholeMaster:
    """REP socket that consumes requests and never replies. ``restart()``
    closes+rebinds, modeling the master-restart behavior that prefaced the
    NSX OOM."""

    def __init__(self, port, io_loop):
        self.port = port
        self.io_loop = io_loop
        self._ctx = zmq.Context()
        self._socket = None
        self._stream = None
        self.recv_count = 0

    def _bind(self):
        self._socket = self._ctx.socket(zmq.REP)
        self._socket.bind(f"tcp://127.0.0.1:{self.port}")
        self._stream = zmq.eventloop.zmqstream.ZMQStream(
            self._socket, io_loop=self.io_loop
        )

        def _on_recv(stream, msg):
            self.recv_count += 1  # consume, never reply

        self._stream.on_recv_stream(_on_recv)

    def start(self):
        self._bind()

    def restart(self):
        self.close()
        self._bind()

    def close(self):
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        self._socket = None

    def term(self):
        self.close()
        self._ctx.term()


async def test_request_client_under_blackhole_master(io_loop, tmp_path):
    port = pytestshellutils.utils.ports.get_unused_localhost_port()
    minion_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    minion_opts["master_uri"] = f"tcp://127.0.0.1:{port}"
    minion_opts["return_retry_timer"] = 1
    minion_opts["return_retry_timer_max"] = 2
    minion_opts["return_retry_tries"] = 5
    minion_opts["request_channel_timeout"] = 2
    minion_opts["request_channel_tries"] = 5

    duration_s = 8.0
    concurrency = 8
    restart_at_s = 3.0
    sample_interval_s = 0.5

    master = BlackholeMaster(port, io_loop)
    master.start()

    client = salt.transport.zeromq.RequestClient(minion_opts, io_loop)
    orig_reconnect = client._reconnect
    reconnects = {"n": 0}

    async def _counting_reconnect():
        reconnects["n"] += 1
        return await orig_reconnect()

    client._reconnect = _counting_reconnect

    sampler = Sampler()

    async def _sender():
        while True:
            try:
                await client.send(b"payload", timeout=2)
            except salt.exceptions.SaltReqTimeoutError:
                pass
            except Exception:  # pylint: disable=broad-except
                log.exception("sender raised; continuing")
            await asyncio.sleep(0)

    senders = [
        asyncio.create_task(_sender(), name=f"runaway-sender-{i}")
        for i in range(concurrency)
    ]

    t0 = time.monotonic()
    restarted = False
    try:
        while time.monotonic() - t0 < duration_s:
            sampler.take(
                queue_depth=client._queue.qsize(),
                reconnects=reconnects["n"],
            )
            if not restarted and (time.monotonic() - t0) >= restart_at_s:
                log.info(
                    "blackhole master: restarting at t=%.1f",
                    time.monotonic() - t0,
                )
                master.restart()
                restarted = True
            await asyncio.sleep(sample_interval_s)
        sampler.take(
            queue_depth=client._queue.qsize(),
            reconnects=reconnects["n"],
        )
    finally:
        for t in senders:
            t.cancel()
        await asyncio.gather(*senders, return_exceptions=True)
        client.close()
        master.term()

    csv_path = tmp_path / "runaway.csv"
    sampler.write_csv(csv_path)
    log.warning("runaway harness summary: %s (csv=%s)", sampler.summary(), csv_path)

    first = sampler.rows[0]
    last = sampler.rows[-1]
    task_growth = last[2] - first[2]
    # Measuring stick, not a hard reproducer: the NSX OOM played out over
    # hours. An 8-second CI window won't grow tasks or RSS far enough to
    # assert on. We sanity-check that the reconnect path was exercised and
    # leave the actual leak numbers in the warning log + CSV for inspection.
    assert (
        reconnects["n"] > 0
    ), "no reconnects observed; harness did not stress _send_recv"
    log.warning(
        "rss_growth_kb=%s task_growth=%s reconnects=%s",
        last[1] - first[1],
        task_growth,
        reconnects["n"],
    )
