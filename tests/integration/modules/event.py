# -*- coding: utf-8 -*-
'''
    tests.integration.modules.event
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
'''

import time
import threading
from Queue import Queue, Empty

import integration

from salt.utils import event

class EventModuleTest(integration.ModuleCase):
    def test_event_fire_master(self):
        events = Queue()

        def get_event(events):
            me = event.MasterEvent(self.master_opts['sock_dir'])
            events.put_nowait(
                me.get_event(wait=5, tag='salttest', full=False)
            )

        threading.Thread(target=get_event, args=(events,)).start()
        time.sleep(1)   # Allow multiprocessing.Process to start

        ret = self.run_function(
            'event.fire_master',
            ['event.fire_master: just test it!!!!', 'salttest']
        )
        self.assertTrue(ret)

        eventfired = events.get(block=True, timeout=1)
        self.assertIn('event.fire_master: just test it!!!!', eventfired['data'])

        ret = self.run_function(
            'event.fire_master',
            ['event.fire_master: just test it!!!!', 'salttest-miss']
        )
        self.assertTrue(ret)

        with self.assertRaises(Empty):
            eventfired = events.get(block=True, timeout=1)

    def test_event_fire(self):
        events = Queue()

        def get_event(events):
            me = event.MinionEvent(**self.minion_opts)
            events.put_nowait(
                me.get_event(wait=5, tag='salttest', full=False)
            )

        threading.Thread(target=get_event, args=(events,)).start()
        time.sleep(1)   # Allow multiprocessing.Process to start

        ret = self.run_function(
            'event.fire', ['event.fire: just test it!!!!', 'salttest']
        )
        self.assertTrue(ret)

        eventfired = events.get(block=True, timeout=5)
        self.assertIn('event.fire: just test it!!!!', eventfired)

        ret = self.run_function(
            'event.fire', ['event.fire: just test it!!!!', 'salttest-miss']
        )
        self.assertTrue(ret)

        with self.assertRaises(Empty):
            eventfired = events.get(block=True, timeout=1)

    def test_event_fire_ipc_mode_tcp(self):
        events = Queue()

        def get_event(events):
            me = event.MinionEvent(**self.sub_minion_opts)
            events.put_nowait(
                me.get_event(wait=5, tag='salttest', full=False)
            )

        threading.Thread(target=get_event, args=(events,)).start()
        time.sleep(1)   # Allow multiprocessing.Process to start

        ret = self.run_function(
            'event.fire', ['event.fire: just test it!!!!', 'salttest'],
            minion_tgt='sub_minion'
        )
        self.assertTrue(ret)

        eventfired = events.get(block=True, timeout=5)
        self.assertIn('event.fire: just test it!!!!', eventfired)

        ret = self.run_function(
            'event.fire', ['event.fire: just test it!!!!', 'salttest-miss'],
            minion_tgt='sub_minion'
        )
        self.assertTrue(ret)

        with self.assertRaises(Empty):
            eventfired = events.get(block=True, timeout=1)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(EventModuleTest)
