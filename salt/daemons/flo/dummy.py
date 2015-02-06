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

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import ioflo.base.deeding

log = logging.getLogger(__name__)


class SaltDummyPublisher(ioflo.base.deeding.Deed):
    '''
    A dummy publisher that transparently redirects publications to 
    a translation system to have them mocked up and sent back into a router
    '''
    Ioinits = {
            'opts': '.salt.opts',
            'publish': '.salt.var.publish'
            }

    def action(self):
        while self.publish.value:
            log.debug('Dummy publisher publishing: {0}'.format(
                self.publish.value.popleft()
                )
            )
