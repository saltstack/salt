"""
    tests.support.events
    ~~~~~~~~~~~~~~~~~~~~
"""

import multiprocessing
import os
import time
from contextlib import contextmanager

import salt.utils.event
from salt.utils.process import Process, clean_proc


@contextmanager
def eventpublisher_process(sock_dir):
    opts = {
        "sock_dir": sock_dir,
        "interface": "127.0.0.1",
        "publish_port": 4506,
        "ipv6": None,
        "zmq_filtering": None,
    }
    ipc_publisher = salt.transport.publish_server(
        opts,
        pub_path=os.path.join(opts["sock_dir"], "master_event_pub.ipc"),
        pull_path=os.path.join(opts["sock_dir"], "master_event_pull.ipc"),
        transport="tcp",
    )
    proc = Process(
        target=ipc_publisher.publish_daemon,
        args=[
            ipc_publisher.publish_payload,
        ],
    )
    # proc = salt.utils.event.EventPublisher({"sock_dir": sock_dir})
    proc.start()
    try:
        if os.environ.get("TRAVIS_PYTHON_VERSION", None) is not None:
            # Travis is slow
            time.sleep(10)
        else:
            time.sleep(8)
        yield
    finally:
        clean_proc(proc)


class EventSender(multiprocessing.Process):
    def __init__(self, data, tag, wait, sock_dir):
        super().__init__()
        self.data = data
        self.tag = tag
        self.wait = wait
        self.sock_dir = sock_dir

    def run(self):
        with salt.utils.event.MasterEvent(self.sock_dir, listen=False) as me:
            time.sleep(self.wait)
            me.fire_event(self.data, self.tag)
            # Wait a few seconds before tearing down the zmq context
            if os.environ.get("TRAVIS_PYTHON_VERSION", None) is not None:
                # Travis is slow
                time.sleep(10)
            else:
                time.sleep(2)


@contextmanager
def eventsender_process(data, tag, sock_dir, wait=0):
    proc = EventSender(data, tag, wait, sock_dir=sock_dir)
    proc.start()
    try:
        yield
    finally:
        clean_proc(proc)
