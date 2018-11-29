# -*- coding: utf-8 -*-
'''

    integration.reactor.reactor
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's reactor system
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt testing libs
from tests.support.case import ShellTestCase
from tests.support.mixins import SaltMinionEventAssertsMixin
from tests.support.unit import skipIf
from tests.support.helpers import flaky

# Import Salt libs
import salt.utils.event
import salt.utils.reactor
import signal


class TimeoutException(Exception):
    pass


class ReactorTest(ShellTestCase, SaltMinionEventAssertsMixin):
    '''
    Test Salt's reactor system
    '''
    def setUp(self):
        self.timeout = 30

    def get_event(self, class_type='master'):
        return salt.utils.event.get_event(
            class_type,
            sock_dir=self.master_opts['sock_dir'],
            transport=self.master_opts['transport'],
            keep_loop=True,
            opts=self.master_opts)

    def fire_event(self, tag, data):
        event = self.get_event()
        event.fire_event(tag, data)

    def alarm_handler(self, signal, frame):
        raise TimeoutException('Timeout of {0} seconds reached'.format(self.timeout))

    @flaky
    def test_ping_reaction(self):
        '''
        Fire an event on the master and ensure
        that it pings the minion
        '''
        # Create event bus connection
        e = salt.utils.event.get_event('minion', sock_dir=self.minion_opts['sock_dir'], opts=self.minion_opts)

        e.fire_event({'a': 'b'}, '/test_event')

        self.assertMinionEventReceived({'a': 'b'})

    @skipIf(salt.utils.platform.is_windows(), 'no sigalarm on windows')
    def test_reactor_local_reaction(self):
        '''
        Fire an event on the master and ensure
        The reactor event responds with localclient
        '''
        signal.signal(signal.SIGALRM, self.alarm_handler)
        signal.alarm(self.timeout)

        master_event = self.get_event()
        master_event.fire_event({'id': 'minion'}, 'salt/test/reactor/local')

        try:
            while True:
                event = master_event.get_event(full=True)

                if event is None:
                    continue

                if event.get('tag') == 'test_reaction':
                    self.assertTrue(event['data']['data']['test_reaction'])
                    break
        finally:
            signal.alarm(0)

    @skipIf(salt.utils.platform.is_windows(), 'no sigalarm on windows')
    def test_reactor_runner_reaction(self):
        '''
        Fire an event on the master and ensure
        The reactor event responds with a runner client
        '''
        signal.signal(signal.SIGALRM, self.alarm_handler)
        signal.alarm(self.timeout)

        master_event = self.get_event()
        master_event.fire_event({'id': 'minion'}, 'salt/test/reactor/runner')

        try:
            while True:
                event = master_event.get_event(full=True)

                if event is None:
                    continue

                if event.get('tag') == 'test_reaction':
                    self.assertTrue(event['data']['test_reaction'])
                    break
        finally:
            signal.alarm(0)

    @skipIf(salt.utils.platform.is_windows(), 'no sigalarm on windows')
    def test_reactor_wheel_reaction(self):
        '''
        Fire an event on the master and ensure
        The reactor event responds with a wheel client
        '''
        signal.signal(signal.SIGALRM, self.alarm_handler)
        signal.alarm(self.timeout)

        master_event = self.get_event()
        master_event.fire_event({'id': 'minion'}, 'salt/test/reactor/wheel')

        try:
            while True:
                event = master_event.get_event(full=True)

                if event is None:
                    continue

                if event.get('tag') == 'test_reaction':
                    self.assertTrue(event['data']['test_reaction'])
                    self.assertTrue('foobar' in self.run_key('--list=accepted'))
                    break

        finally:
            signal.alarm(0)

    @skipIf(salt.utils.platform.is_windows(), 'no sigalarm on windows')
    def test_reactor_legacy_reaction(self):
        '''
        Fire an event on the master and ensure
        The reactor event responds with a wheel client
        '''
        signal.signal(signal.SIGALRM, self.alarm_handler)
        signal.alarm(self.timeout)

        master_event = self.get_event()
        master_event.fire_event({'id': 'minion'}, 'salt/test/reactor/legacy')

        try:
            while True:
                event = master_event.get_event(full=True)

                if event is None:
                    continue

                if event.get('tag') == 'test_reaction':
                    self.assertTrue(event['data']['test_reaction'])
                    break

        finally:
            signal.alarm(0)
