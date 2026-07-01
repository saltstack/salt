"""
Timeout scheduling for the Raft node.

Provides manual, threaded, and asynchronous schedulers so election and
heartbeat timers stay outside the core state machine.  Production Salt
runs the consensus event loop inside ``MasterPubServerChannel._publish_daemon``
(Tornado on top of asyncio) and uses :class:`AsyncTimeoutScheduler`; tests
use :class:`ManualTimeoutScheduler` for deterministic time.
"""

import asyncio
import inspect
import logging
import threading
import time

log = logging.getLogger(__name__)


class TimeoutHandle:
    def __init__(self, scheduler, handle, callback):
        self.scheduler = scheduler
        self.handle = handle  # Can be time (float) or asyncio.Handle/Task
        self.callback = callback
        self.cancelled = False

    def cancel(self):
        if self.cancelled:
            return
        self.cancelled = True

        if hasattr(self.handle, "cancel"):
            # asyncio Handle or Task
            self.handle.cancel()
        else:
            # Manual/Threaded float time
            lock = getattr(self.scheduler, "_lock", None)
            if lock:
                with lock:
                    self._do_manual_cancel()
            else:
                self._do_manual_cancel()

    def _do_manual_cancel(self):
        if hasattr(self.scheduler, "timeouts"):
            if self.handle in self.scheduler.timeouts:
                if self.scheduler.timeouts[self.handle] == self.callback:
                    self.scheduler.timeouts.pop(self.handle)


class TimeoutScheduler:
    def __init__(self):
        self.timeouts = {}

    def schedule(self, timeout, callback):
        t = time.monotonic() + timeout
        self.timeouts[t] = callback
        return TimeoutHandle(self, t, callback)

    def process_timeouts(self):
        for t in list(self.timeouts.keys()):
            if time.monotonic() > t:
                cb = self.timeouts.pop(t)
                cb()


class ManualTimeoutScheduler(TimeoutScheduler):
    def __init__(self):
        super().__init__()
        self.timeouts = {}
        self.time = 0

    def schedule(self, timeout, callback):
        t = self.time + timeout
        self.timeouts[t] = callback
        return TimeoutHandle(self, t, callback)

    def advance_clock_to_next_timeout(self):
        if not self.timeouts:
            return
        self.time = sorted(self.timeouts.keys())[0]
        return True

    def process_timeouts(self):
        for t in sorted(list(self.timeouts.keys())):
            if self.time >= t:
                cb = self.timeouts.pop(t)
                cb()

    def process_existing_timeouts(self):
        for t in sorted(list(self.timeouts.keys())):
            cb = self.timeouts.pop(t)
            cb()


class AsyncTimeoutScheduler:
    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()

    def schedule(self, timeout, callback):
        # We need a handle that we can check for cancellation inside the wrapper
        class State:
            cancelled = False

        state = State()

        def _wrapper():
            if state.cancelled:
                return
            if inspect.iscoroutinefunction(callback):
                self.loop.create_task(callback())
            else:
                callback()

        inner_handle = self.loop.call_later(timeout, _wrapper)

        # Create a custom handle that cancels both the state and the timer
        class AsyncHandle:
            def cancel(self):
                state.cancelled = True
                inner_handle.cancel()

        return TimeoutHandle(self, AsyncHandle(), callback)

    def stop(self):
        pass


class ThreadedTimeoutScheduler:
    def __init__(self):
        self.timeouts = {}
        self._lock = threading.Lock()
        self._running = threading.Event()
        self._thread = None

    def start(self):
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=1.0)

    def schedule(self, timeout, callback):
        with self._lock:
            t = time.monotonic() + timeout
            self.timeouts[t] = callback
            return TimeoutHandle(self, t, callback)

    def _run(self):
        while self._running.is_set():
            now = time.monotonic()
            to_call = []
            with self._lock:
                for t in list(self.timeouts.keys()):
                    if now >= t:
                        to_call.append(self.timeouts.pop(t))
            for cb in to_call:
                try:
                    cb()
                except Exception:  # pylint: disable=broad-except
                    log.exception("Error in timeout callback")
            time.sleep(0.01)
