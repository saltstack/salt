# -*- coding: utf-8 -*-
'''
Module for notifications via Twilio

.. versionadded:: Helium

:depends:   - twilio python module
:configuration: Configure this module by specifying the name of a configuration
    profile in the minion config, minion pillar, or master config.

    For example:

    .. code-block:: yaml

        my-twilio-account:
            twilio.account_sid: AC32a3c83990934481addd5ce1659f04d2
            twilio.auth_token: mytoken
'''
import logging

HAS_LIBS = False
try:
    from twilio.rest import TwilioRestClient
    HAS_LIBS = True
except ImportError:
    pass

log = logging.getLogger(__name__)

__virtualname__ = 'twilio'


def __virtual__():
    '''
    Only load this module if twilio is installed on this minion.
    '''
    if HAS_LIBS:
        return __virtualname__
    return False


def _get_twilio(profile):
    '''
    Return the twilio connection
    '''
    creds = __salt__['config.option'](profile)
    client = TwilioRestClient(
        creds.get('twilio.account_sid'),
        creds.get('twilio.auth_token'),
    )

    return client


def send_sms(profile, body, to, from_):
    '''
    Send an sms

    CLI Example:

        twilio.send_sms twilio-account '+18019999999' '+18011111111' 'Test sms'
    '''
    ret = {
            'message.sid': None,
          }
    client = _get_twilio(profile)
    message = client.sms.messages.create(body=body, to=to, from_=from_)
    ret['message.sid'] = message.sid
    log.info(ret)
    return ret
