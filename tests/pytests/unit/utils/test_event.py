import asyncio
import logging
import os

import salt.utils.event
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


class res:
    tag = None
    data = None


def _handle_publish(raw):
    res.tag, res.data = salt.utils.event.SaltEvent.unpack(raw)
    # self.stop()


async def test_event_subscription():
    io_loop = asyncio.get_event_loop()
    sock_dir = os.path.join(RUNTIME_VARS.TMP, "test-socks")
    opts = {"sock_dir": sock_dir}
    if not os.path.exists(sock_dir):
        os.makedirs(sock_dir)
    # self.addCleanup(shutil.rmtree, self.sock_dir, ignore_errors=True)
    publisher = salt.utils.event.AsyncEventPublisher(
        opts,
        io_loop,
    )
    await publisher.start()

    event = salt.utils.event.get_event("minion", opts=opts, io_loop=io_loop)
    event.subscribe("")
    event.set_event_handler(_handle_publish)
    with salt.utils.event.MinionEvent(opts, listen=True) as me:
        me.fire_event({"data": "foo1"}, "evt1")
        await asyncio.sleep(0.3)
        evt1 = me.get_event(tag="evt1")
        assert res.tag == "evt1"
        res.data.pop("_stamp")  # drop the stamp
        assert res.data == {"data": "foo1"}

    if me.subscriber:
        log.error("HAS SUB")
    if me.pusher:
        log.error("HAS PUSh")

    publisher.publisher.close()
    await publisher.publisher.server.wait_closed()
    publisher.puller.close()
    await publisher.puller.server.wait_closed()


async def test_event_unsubscribe_remove_error():
    sock_dir = os.path.join(RUNTIME_VARS.TMP, "test-socks")
    opts = {"sock_dir": sock_dir}
    with salt.utils.event.MinionEvent(opts, listen=True) as me:
        tag = "evt1"
        me.fire_event({"data": "foo1"}, tag)

        # Make sure no remove error is raised when tag is not found
        for _ in range(2):
            me.unsubscribe(tag)

        me.unsubscribe("tag_does_not_exist")
