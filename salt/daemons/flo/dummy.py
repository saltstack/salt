# -*- coding: utf-8 -*-
'''
The dummy publisher for the Salt Master

Contains functionality to short-circuit a salt-master's
publish functionality so that instead of publications being
sent across the wire, they are instead transparently redirected
to a returner.

Designed for use primarily in load-testing the salt-master
without the need for a swarm of real minions.
'''

# pylint: disable=W0232
# pylint: disable=3rd-party-module-not-gated

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import salt libs
import ioflo.base.deeding
import salt.utils.stringutils

log = logging.getLogger(__name__)


class SaltDummyPublisher(ioflo.base.deeding.Deed):
    '''
    A dummy publisher that transparently redirects publications to
    a translation system to have them mocked up and sent back into a router
    '''
    Ioinits = {
            'opts': salt.utils.stringutils.to_str('.salt.opts'),
            'publish': salt.utils.stringutils.to_str('.salt.var.publish'),
            'lane_stack': salt.utils.stringutils.to_str('.salt.lane.manor.stack'),
            'workers': salt.utils.stringutils.to_str('.salt.track.workers'),
            }

    def action(self):
        while self.publish.value:
            pub = self.publish.value.popleft()
            log.debug('Dummy publisher publishing: %s', pub)
            msg = self._fill_tmpl(pub)
            self.lane_stack.value.transmit(msg, self.lane_stack.value.fetchUidByName(next(self.workers.value)))

    def _fill_tmpl(self, pub):
        '''
        Takes a template and a job and fills the template with
        fake return data associated with the job
        '''
        msg = {'load': {
                    'fun_args': [],
                    'jid': pub['return']['pub']['jid'],
                    'return': True,
                    'retcode': 0,
                    'success': True,
                    'cmd': '_return',
                    'fun': 'test.ping',
                    'id': 'silver'
               },
               'route': {
                    'src': ('silver_minion', 'jobber50e73ccefd052167c7', 'jid_ret'),
                    'dst': ('silver_master_master', None, 'remote_cmd')
                }
               }

        log.debug('Dummy publisher faking return with: %s', msg)
        return msg
