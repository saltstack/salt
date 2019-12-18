# -*- coding: utf-8 -*-
'''
    tests.support.events
    ~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals
import os
import time
import multiprocessing
from contextlib import contextmanager

# Import Salt libs
import salt.utils.event
from salt.utils.process import clean_proc


@contextmanager
def eventpublisher_process(sock_dir):
    proc = salt.utils.event.EventPublisher({'sock_dir': sock_dir})
    proc.start()
    try:
        if os.environ.get('TRAVIS_PYTHON_VERSION', None) is not None:
            # Travis is slow
            time.sleep(10)
        else:
            time.sleep(2)
        yield
    finally:
        clean_proc(proc)


class EventSender(multiprocessing.Process):
    def __init__(self, data, tag, wait, sock_dir):
        super(EventSender, self).__init__()
        self.data = data
        self.tag = tag
        self.wait = wait
        self.sock_dir = sock_dir

    def run(self):
        me = salt.utils.event.MasterEvent(self.sock_dir, listen=False)
        time.sleep(self.wait)
        me.fire_event(self.data, self.tag)
        # Wait a few seconds before tearing down the zmq context
        if os.environ.get('TRAVIS_PYTHON_VERSION', None) is not None:
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
