"""
Surgical reproducer for the ``_publish_tasks`` accumulation bug behind an
observed salt-minion OOM under sustained master backpressure.

Before the fix in ``salt/utils/event.py``, every ``SaltEvent.fire_event()``
call in async mode appended a Task to ``self._publish_tasks`` and nothing
pruned it until ``close_pull()``. Under sustained event firing the list
grew linearly forever.

This test stubs ``SaltEvent.pusher.publish`` so each publish coroutine
completes immediately, fires N events, lets them drain, and asserts the
``_publish_tasks`` set is empty. The fix uses ``set.add_done_callback`` so
completed tasks self-evict; without it, every fired event would still be in
the set.
"""

import asyncio
import logging

import salt.config
import salt.utils.event
from tests.support.mock import MagicMock

log = logging.getLogger(__name__)


async def test_publish_tasks_accumulate_under_slow_pusher():
    n_events = 2000
    loop = asyncio.get_running_loop()
    opts = salt.config.DEFAULT_MINION_OPTS.copy()

    event = salt.utils.event.SaltEvent(
        node="minion", opts=opts, listen=False, io_loop=loop
    )
    # Skip the real IPC publisher: pretend we're already connected and stub
    # the pusher so each publish() returns an immediately-completing
    # coroutine. Mirrors a healthy-but-slow pusher.
    event.cpush = True
    event._run_io_loop_sync = False

    async def _publish(_msg):
        await asyncio.sleep(0)

    event.pusher = MagicMock()
    event.pusher.publish.side_effect = _publish

    try:
        for i in range(n_events):
            event.fire_event({"i": i}, "salt/runaway/test")

        # Let every scheduled publish task complete.
        for _ in range(5):
            await asyncio.sleep(0)

        retained = len(event._publish_tasks)
        log.info("publish-tasks scenario: fired=%s retained=%s", n_events, retained)
        assert retained == 0, (
            f"_publish_tasks retained {retained} of {n_events} fired events "
            "after every publish() coroutine completed. Done tasks are not "
            "being pruned from the set; under sustained event firing this "
            "is a memory runaway."
        )
    finally:
        for task in list(event._publish_tasks):
            task.cancel()
        event._publish_tasks.clear()
