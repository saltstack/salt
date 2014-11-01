# -*- coding: utf-8 -*-

'''


'''


import logging
import salt.utils
import salt.returners

log = logging.getLogger(__name__)

try:
    from twilio.rest import TwilioRestClient
    HAS_TWILIO = True
expcet ImportError:
    HAS_TWILIO = False

__virtualname__ = 'twilio'

def __virtual__():
    if HAS_TWILIO:
        return __virtualname__
    else:
        return False


def _get_options(ret):
    '''
    Returns options used for the twilio returner.
    '''
    attrs = {'host': 'host',
             'port': 'port',
             'skip': 'skip_on_error',
             'mode': 'mode'}

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    return _options


