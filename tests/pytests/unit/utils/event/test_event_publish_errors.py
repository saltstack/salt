"""A failed publish drops the event and says why, or raises, depending on the flag."""

import logging

import pytest

import salt.transport.tcp
import salt.utils.event
from tests.support.mock import AsyncMock, MagicMock


@pytest.fixture(params=[True, False], ids=["flag_on", "flag_off"])
def event(request, master_opts):
    evt = object.__new__(salt.utils.event.SaltEvent)
    evt.opts = dict(master_opts, master_async_mworker=request.param)
    evt.cpush = True
    evt._run_io_loop_sync = False
    evt.pusher = MagicMock()
    evt.pusher.publish = AsyncMock(
        side_effect=salt.transport.tcp.ClosingError(
            "Publish server for /run/event.ipc was already closed by close()"
            " and is still being used"
        )
    )
    return evt


async def test_fire_event_async_drops_or_raises(event, caplog):
    with caplog.at_level(logging.WARNING, logger="salt.utils.event"):
        if event.opts["master_async_mworker"]:
            await event.fire_event_async({"a": 1}, "salt/test/tag")
        else:
            with pytest.raises(salt.transport.tcp.ClosingError):
                await event.fire_event_async({"a": 1}, "salt/test/tag")
    if event.opts["master_async_mworker"]:
        # The tag, the exception type and the message are all in the log.
        assert "dropping event tag=salt/test/tag" in caplog.text
        assert "ClosingError" in caplog.text
        assert "was already closed by close()" in caplog.text
    else:
        assert not caplog.records
