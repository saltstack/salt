import logging
import random
import threading
import time

import psutil
import pytest

import salt.config
import salt.utils.event
from tests.support.mock import patch

log = logging.getLogger()  # __name__)


@pytest.fixture
def stop_event():
    """
    Event used to signal starting and stopping of test
    """
    evt = threading.Event()
    try:
        yield evt
    finally:
        log.info("Clear threading event")
        evt.clear()


@pytest.fixture
def opts(tmp_path):
    """
    opts needed for master events
    """
    opts = salt.config.master_config("")
    sock_dir = tmp_path / "sock"
    sock_dir.mkdir()
    opts["sock_dir"] = str(sock_dir)
    return opts


@pytest.fixture
def process_manager():
    """
    Process manager fixture.

    Terminates process manager processes on teardown.
    """
    process_manager = salt.utils.process.ProcessManager(wait_for_kill=5)
    try:
        yield process_manager
    finally:
        log.info("Terminate process manager processes")
        process_manager.terminate()


@pytest.fixture
def publisher(process_manager, opts):
    """
    Event Publisher process.
    """
    proc = process_manager.add_process(
        salt.utils.event.EventPublisher,
        args=(opts,),
        name="EventPublisher",
    )
    yield proc


def _publish_target(evt, opts):
    """
    Publish many large events to the event publisher
    """
    n = 0
    event = salt.utils.event.get_event("master", opts=opts, listen=False)
    log.info("Waiting for start event")
    evt.wait(5)
    log.info("Start publishing")
    try:
        while evt.is_set():
            n += 1
            size = random.randint(500, 5000)
            event.fire_event({"n": n, "data": "0" * size}, "/meh")
            time.sleep(0.02)
    finally:
        event.destroy()


@pytest.fixture
def publish(opts, stop_event):
    """
    Run publish events in thread.
    """
    log.info("Publiash fixture")
    thread = threading.Thread(
        target=_publish_target,
        args=(
            stop_event,
            opts,
        ),
    )
    thread.start()
    time.sleep(0.2)
    try:
        yield thread
    finally:
        log.info("Join publish thread")
        thread.join()


def _listeners_target(evt, opts):
    """
    Create a hand full of listening events.

    Each listener will pull a single event of the event bus and the stop
    comsuming.
    """
    log.info("Listener wait start")
    evt.wait(5)
    time.sleep(0.2)
    listeners = []
    for i in range(5):
        listeners.append(salt.utils.event.get_event("master", opts=opts, listen=True))
    try:
        for n, listener in enumerate(listeners):
            log.info("Wait for event")
            e = listener.get_event()
            log.info("Listener %d Got event %r", n, e)
            assert e
        while evt.is_set():
            time.sleep(0.02)
    finally:
        log.info("Destroy listeners")
        for listener in listeners:
            listener.destroy()


@pytest.fixture
def listeners(opts, stop_event):
    """
    Non consuming listeners
    """
    thread = threading.Thread(
        target=_listeners_target,
        args=(
            stop_event,
            opts,
        ),
    )
    thread.start()
    time.sleep(0.2)
    try:
        yield thread
    finally:
        log.info("Join listeners thread")
        thread.join()


def test_fire_event_recovers_after_pusher_send_failure(publisher, opts):
    """
    Regression test for https://github.com/saltstack/salt/issues/69914

    A failed ``pusher.send()`` (e.g. the ``FileNotFoundError`` raised by a
    stale IPC stream after ``EventPublisher`` is restarted) must not
    permanently wedge the event bus for the lifetime of the ``SaltEvent``
    instance. Before the fix, every subsequent ``fire_event()`` call kept
    hitting the same dead pusher forever; after the fix, the broken pusher
    is dropped and the next call transparently reconnects and delivers.

    This exercises the real ``SyncWrapper`` + threaded ``IOLoop`` +
    ``IPCMessageClient`` stack used by master worker processes (only the
    innermost ``send()`` call is faked, to deterministically reproduce the
    failure without racing the actual epoll bug), against a real, running
    ``EventPublisher`` process.
    """
    event = salt.utils.event.get_event("master", opts=opts, listen=False)
    try:
        # Establish a real, connected pusher against the live EventPublisher.
        assert event.fire_event({"data": "foo1"}, "evt1") is True
        assert event.cpush is True

        # Simulate the real-world failure: the underlying IPCMessageClient's
        # send() raises inside the SyncWrapper's worker thread.
        with patch.object(
            event.pusher.obj,
            "send",
            side_effect=FileNotFoundError(2, "No such file or directory"),
        ):
            with pytest.raises(FileNotFoundError):
                event.fire_event({"data": "foo2"}, "evt2")

        # The broken pusher must be dropped, not reused.
        assert event.cpush is False
        assert event.pusher is None

        # The next fire_event() call must reconnect and actually deliver,
        # instead of raising the same exception forever.
        listener = salt.utils.event.get_event("master", opts=opts, listen=True)
        try:
            assert event.fire_event({"data": "foo3"}, "evt3") is True
            evt = listener.get_event(tag="evt3", wait=10, match_type="startswith")
            assert evt is not None
            assert evt["data"] == "foo3"
        finally:
            listener.destroy()
    finally:
        event.destroy()


def test_publisher_mem(publisher, publish, listeners, stop_event):
    """
    Test event publisher memory consumption.
    """
    start = time.time()

    # Memory consumption before any publishing happens
    baseline = psutil.Process(publisher.pid).memory_info().rss / 1024**2
    log.info("Baseline is %d MB", baseline)
    stop_event.set()
    log.info("Stop event has been set")
    try:
        # After the loader tests run we have a baseline of almost 300MB
        # assert baseline < 150
        leak_threshold = baseline + 100 + (baseline * 0.5)
        while time.time() - start < 60:
            assert publisher.is_alive()
            mem = psutil.Process(publisher.pid).memory_info().rss / 1024**2
            log.info(
                "Publisher process memory consuption %d MB after %d seconds",
                mem,
                time.time() - start,
            )
            assert mem < leak_threshold
            time.sleep(1)
    # except Exception as exc:
    #    log.exception("WTF")
    finally:
        log.info("test_publisher_mem finished succesfully")
        stop_event.clear()
