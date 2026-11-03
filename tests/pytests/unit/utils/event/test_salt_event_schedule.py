"""
Unit tests for SaltEvent._schedule coroutine-function detection.

Verifies that _schedule uses inspect.iscoroutinefunction (not the deprecated
asyncio.iscoroutinefunction) so no DeprecationWarning is emitted on Python 3.12+.
"""

import asyncio
import warnings

from salt.utils.event import SaltEvent


def _make_salt_event(loop):
    """Create a minimal SaltEvent instance with an asyncio loop attached."""
    evt = SaltEvent.__new__(SaltEvent)
    evt.io_loop = loop
    evt._run_io_loop_sync = False
    return evt


def test_salt_event_schedule_coroutine_no_deprecation_warning():
    """
    SaltEvent._schedule must use inspect.iscoroutinefunction, not the deprecated
    asyncio.iscoroutinefunction, to avoid DeprecationWarning on Python 3.12+.
    """

    async def _body():
        loop = asyncio.get_event_loop()
        evt = _make_salt_event(loop)
        fired = []

        async def coro_func():
            fired.append(1)

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            evt._schedule(coro_func)

        await asyncio.sleep(0.02)
        assert fired == [1], "coroutine function was not called by _schedule"

    asyncio.run(_body())


def test_salt_event_schedule_regular_callable():
    """
    SaltEvent._schedule correctly calls a regular (non-coroutine) callable.
    """

    async def _body():
        loop = asyncio.get_event_loop()
        evt = _make_salt_event(loop)
        fired = []

        def regular_func():
            fired.append(1)

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            evt._schedule(regular_func)

        await asyncio.sleep(0.02)
        assert fired == [1], "regular callable was not called by _schedule"

    asyncio.run(_body())
