import asyncio
import os
import salt.utils.event
from tests.support.runtests import RUNTIME_VARS

class res:
    tag = None
    data = None

def _handle_publish(self, raw):
    res.tag, res.data = salt.utils.event.SaltEvent.unpack(raw)
    #self.stop()

async def test_event_subscription():
    io_loop = asyncio.get_event_loop()
    sock_dir = os.path.join(RUNTIME_VARS.TMP, "test-socks")
    if not os.path.exists(sock_dir):
        os.makedirs(sock_dir)
    #self.addCleanup(shutil.rmtree, self.sock_dir, ignore_errors=True)
    opts = {"sock_dir": self.sock_dir}
    publisher = salt.utils.event.AsyncEventPublisher(
        opts,
        io_loop,
    )
    event = salt.utils.event.get_event(
        "minion", opts=opts, io_loop=io_loop
    )
    event.subscribe("")
    event.set_event_handler(_handle_publish)
    with salt.utils.event.MinionEvent(self.opts, listen=True) as me:
        me.fire_event({"data": "foo1"}, "evt1")
        await asyncio.sleep(.3)
        evt1 = me.get_event(tag="evt1")
        assert res.tag == "evt1"
        res.data.pop("_stamp")  # drop the stamp
        assert data == {"data": "foo1"}


async def test_event_unsubscribe_remove_error():
    opts = {"sock_dir": self.sock_dir}
    with salt.utils.event.MinionEvent(opts, listen=True) as me:
        tag = "evt1"
        me.fire_event({"data": "foo1"}, tag)

        # Make sure no remove error is raised when tag is not found
        for _ in range(2):
            me.unsubscribe(tag)

        me.unsubscribe("tag_does_not_exist")
