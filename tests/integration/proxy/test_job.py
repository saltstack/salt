# -*- coding: utf-8 -*-
'''

    tests.integration.minion.test_job
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase

# Import salt libs
from tests.support.mixins import SaltMinionEventAssertsMixin


class ProxyJobTest(SaltMinionEventAssertsMixin, ModuleCase):

    def test_ack_event(self):
        jid = '20191116163929293207'

        ret = self.run_function(
            'test.ping',
            jid=jid,
            minion_tgt='proxytest'
        )
        self.assertTrue(ret)

        self.assertMinionEventFired("salt/job/{0}/ack/proxytest".format(jid))

    def test_ack_event_multijob(self):
        jid = '20191116163929293208'

        ret = self.run_function(
            ['test.ping', 'test.true'],
            jid=jid,
            minion_tgt='proxytest'
        )
        self.assertTrue(ret)

        self.assertMinionEventFired("salt/job/{0}/ack/proxytest".format(jid))
