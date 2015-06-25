# -*- coding: utf-8 -*-
'''
Provide authentication using Kerberos by trusting webapp. 

This is a placeholder auth module that does not authenticate with kerberos

.. versionadded:: TODO
'''

from __future__ import absolute_import
import logging

log = logging.getLogger(__name__)


def auth(username, **kwargs):
    '''
    Refuse authentication always. This gives the opportunity to use
    the Remote User mecanism in salt-api

    This prevents a local user from bypassing authorisation 

    TOOD : link to documentation about how to enable X-Remote-User in salt-api

    '''
    log.debug('returning False for kerberos trusted auth')
    return False
    
