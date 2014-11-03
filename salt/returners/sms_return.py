# -*- coding: utf-8 -*-

'''
Return data to a mysql server

:maintainer:    Damian Myerscough
:maturity:      new
:depends:       twilio
:platform:      all

To enable this returner the minion will need the python twilio library
installed and the following values configured in the minion or master
config::

    twilio.sid: 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    twilio.token: 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    twilio.to: '+1415XXXXXXX'
    twilio.from: '+1650XXXXXXX'

To use the sms returner, append '--return sms' to the salt command. ex:

    salt '*' test.ping --return sms

'''


import logging

import salt.utils
import salt.returners

log = logging.getLogger(__name__)

try:
    from twilio.rest import TwilioRestClient
    from twilio.rest.exceptions import TwilioRestException
    HAS_TWILIO = True
except ImportError:
    HAS_TWILIO = False

__virtualname__ = 'sms'


def __virtual__():
    if HAS_TWILIO:
        return __virtualname__
    else:
        return False


def _get_options(ret=None):
    '''
    Get the Twilio options from salt.
    '''
    attrs = {'sid': 'sid',
             'token': 'token',
             'to': 'to',
             'from': 'from'}

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    return _options


def returner(ret):
    '''
    Return a response in an SMS message
    '''
    _options = _get_options(ret)

    sid = _options.get('sid', None)
    token = _options.get('token', None)
    sender = _options.get('from', None)
    reciver = _options.get('to', None)

    if sid is None or token is None:
        log.error('Twilio sid/authentication token missing')
        return None

    if sender is None or reciver is None:
        log.error('Twilio to/from fields are missing')
        return None

    client = TwilioRestClient(sid, token)

    try:
        message = client.messages.create(
            body='Minion: {0}\nCmd: {1}\nSuccess: {2}\n\nJid: {3}'.format(
                ret['id'], ret['fun'], ret['success'], ret['jid']
            ), to=reciver, from_=sender)
    except TwilioRestException as e:
        log.error('Twilio [https://www.twilio.com/docs/errors/{0}]'.format(
            e.code))
        return False

    return True
