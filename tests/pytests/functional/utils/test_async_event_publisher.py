"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.unit.utils.event_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import os
import shutil

import pytest
import salt.config
import salt.ext.tornado.ioloop
import salt.utils.event
import salt.utils.stringutils
from tests.support.runtests import RUNTIME_VARS

pytestmark = [pytest.mark.windows_whitelisted]


class IOLoopContainer:
    def stop(self):
        self.io_loop.stop()
        self.publisher.close()
        self.event.destroy()

    def _handle_publish(self, raw):
        self.tag, self.data = salt.utils.event.SaltEvent.unpack(raw)
        self.stop()


@pytest.fixture()
def io_cont(io_loop):
    io_cont = IOLoopContainer()
    io_cont.io_loop = io_loop
    io_cont.sock_dir = os.path.join(RUNTIME_VARS.TMP, "test-socks")
    if not os.path.exists(io_cont.sock_dir):
        os.makedirs(io_cont.sock_dir)
    io_cont.opts = {"sock_dir": io_cont.sock_dir}
    io_cont.publisher = salt.utils.event.AsyncEventPublisher(
        io_cont.opts,
        io_cont.io_loop,
    )
    io_cont.event = salt.utils.event.get_event(
        "minion", opts=io_cont.opts, io_loop=io_cont.io_loop
    )
    io_cont.event.subscribe("")
    io_cont.event.set_event_handler(io_cont._handle_publish)
    yield io_cont
    shutil.rmtree(io_cont.sock_dir, ignore_errors=True)


def test_event_subscription(io_cont):
    """Test a single event is received"""
    with salt.utils.event.MinionEvent(io_cont.opts, listen=True) as me:
        me.fire_event({"data": "foo1"}, "evt1")
        # Make sure the io_loop stops, always
        io_cont.io_loop.add_timeout(io_cont.io_loop.time() + 5, io_cont.io_loop.stop)
        # _handle_publish should stop the io_loop
        io_cont.io_loop.start()
        evt1 = me.get_event(tag="evt1")
        assert io_cont.tag == "evt1"
        io_cont.data.pop("_stamp")  # drop the stamp
        assert io_cont.data == {"data": "foo1"}


def test_event_unsubscribe_remove_error(io_cont):
    with salt.utils.event.MinionEvent(io_cont.opts, listen=True) as me:
        tag = "evt1"
        me.fire_event({"data": "foo1"}, tag)

        # Make sure no remove error is raised when tag is not found
        for _ in range(2):
            me.unsubscribe(tag)

        me.unsubscribe("tag_does_not_exist")
