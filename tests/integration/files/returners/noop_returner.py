# -*- coding: utf-8 -*-
'''
noop_returner
~~~~~~~~~~~~~

A returner that does nothing which is used to test the salt-master `event_return` functionality
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt libs
import salt.utils.jid


log = logging.getLogger(__name__)

__virtualname__ = 'runtests_noop'


def __virtual__():
    return True


def event_return(events):
    log.debug('NOOP_RETURN.event_return - Events: %s', events)


def returner(ret):
    log.debug('NOOP_RETURN.returner - Ret: %s', ret)


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid(__opts__)
