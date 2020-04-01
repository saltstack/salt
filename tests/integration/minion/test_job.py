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


class MinionJobTest(SaltMinionEventAssertsMixin, ModuleCase):

    def test_ack_event(self):
        jid = '20191116163929293205'

        ret = self.run_function(
            'test.ping',
            jid=jid
        )
        self.assertTrue(ret)

        self.assertMinionEventFired("salt/job/{0}/ack/minion".format(jid))

    def test_ack_event_sub_minion(self):
        jid = '20191116163929293210'

        ret = self.run_function(
            'test.ping',
            jid=jid,
            minion_tgt='sub_minion'
        )
        self.assertTrue(ret)

        self.assertMinionEventFired("salt/job/{0}/ack/sub_minion".format(jid))

    def test_ack_event_multijob(self):
        jid = '20191116163929293206'

        ret = self.run_function(
            ['test.ping', 'test.true'],
            jid=jid
        )
        self.assertTrue(ret)

        self.assertMinionEventFired("salt/job/{0}/ack/minion".format(jid))

    def test_ack_event_multijob_sub_minion(self):
        jid = '20191116163929293206'

        ret = self.run_function(
            ['test.ping', 'test.true'],
            jid=jid,
            minion_tgt='sub_minion'
        )
        self.assertTrue(ret)

        self.assertMinionEventFired("salt/job/{0}/ack/sub_minion".format(jid))
