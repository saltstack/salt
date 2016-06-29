# -*- coding: utf-8 -*-
'''

    integration.test_reactor.test_reactor
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's reactor system
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
import integration
import salt.utils.event


class ReactorTest(integration.ModuleCase, integration.SaltMinionEventAssertsMixIn):
    '''
    Test Salt's reactor system
    '''

    def test_ping_reaction(self):
        '''
        Fire an event on the master and ensure
        that it pings the minion
        '''
        # Create event bus connection
        e = salt.utils.event.get_event('minion', sock_dir=self.minion_opts['sock_dir'], opts=self.minion_opts)

        e.fire_event({'a': 'b'}, '/test_event')

        self.assertMinionEventReceived({'a': 'b'})
