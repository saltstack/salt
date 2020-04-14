# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.modules.event
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

# Import python libs
from __future__ import absolute_import

import threading
import time

# Import salt libs
import salt.utils.event as event

# Import 3rd-party libs
from salt.ext.six.moves.queue import (  # pylint: disable=import-error,no-name-in-module
    Empty,
    Queue,
)

# Import Salt Testing libs
from tests.support.case import ModuleCase


class EventModuleTest(ModuleCase):
    def __test_event_fire_master(self):
        events = Queue()

        def get_event(events):
            me = event.MasterEvent(self.master_opts["sock_dir"], listen=True)
            events.put_nowait(me.get_event(wait=10, tag="salttest", full=False))

        threading.Thread(target=get_event, args=(events,)).start()
        time.sleep(1)  # Allow multiprocessing.Process to start

        ret = self.run_function(
            "event.fire_master", ["event.fire_master: just test it!!!!", "salttest"]
        )
        self.assertTrue(ret)

        eventfired = events.get(block=True, timeout=10)
        self.assertIsNotNone(eventfired)
        self.assertIn("event.fire_master: just test it!!!!", eventfired["data"])

        ret = self.run_function(
            "event.fire_master",
            ["event.fire_master: just test it!!!!", "salttest-miss"],
        )
        self.assertTrue(ret)

        with self.assertRaises(Empty):
            eventfired = events.get(block=True, timeout=10)

    def __test_event_fire(self):
        events = Queue()

        def get_event(events):
            me = event.MinionEvent(self.minion_opts, listen=True)
            events.put_nowait(me.get_event(wait=10, tag="salttest", full=False))

        threading.Thread(target=get_event, args=(events,)).start()
        time.sleep(1)  # Allow multiprocessing.Process to start

        ret = self.run_function(
            "event.fire", ["event.fire: just test it!!!!", "salttest"]
        )
        self.assertTrue(ret)

        eventfired = events.get(block=True, timeout=10)
        self.assertIsNotNone(eventfired)
        self.assertIn("event.fire: just test it!!!!", eventfired)

        ret = self.run_function(
            "event.fire", ["event.fire: just test it!!!!", "salttest-miss"]
        )
        self.assertTrue(ret)

        with self.assertRaises(Empty):
            eventfired = events.get(block=True, timeout=10)

    def __test_event_fire_ipc_mode_tcp(self):
        events = Queue()

        def get_event(events):
            me = event.MinionEvent(self.sub_minion_opts, listen=True)
            events.put_nowait(me.get_event(wait=10, tag="salttest", full=False))

        threading.Thread(target=get_event, args=(events,)).start()
        time.sleep(1)  # Allow multiprocessing.Process to start

        ret = self.run_function(
            "event.fire",
            ["event.fire: just test it!!!!", "salttest"],
            minion_tgt="sub_minion",
        )
        self.assertTrue(ret)

        eventfired = events.get(block=True, timeout=10)
        self.assertIsNotNone(eventfired)
        self.assertIn("event.fire: just test it!!!!", eventfired)

        ret = self.run_function(
            "event.fire",
            ["event.fire: just test it!!!!", "salttest-miss"],
            minion_tgt="sub_minion",
        )
        self.assertTrue(ret)

        with self.assertRaises(Empty):
            eventfired = events.get(block=True, timeout=10)
