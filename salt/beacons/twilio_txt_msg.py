# -*- coding: utf-8 -*-
'''
Beacon to emit Twilio text messages
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals

import logging

from salt.ext import six
from salt.ext.six.moves import map

# Import 3rd Party libs
try:
    import twilio
    # Grab version, ensure elements are ints
    twilio_version = tuple([int(x) for x in twilio.__version_info__])
    if twilio_version > (5, ):
        from twilio.rest import Client as TwilioRestClient
    else:
        from twilio.rest import TwilioRestClient
    HAS_TWILIO = True
except ImportError:
    HAS_TWILIO = False

log = logging.getLogger(__name__)

__virtualname__ = 'twilio_txt_msg'


def __virtual__():
    if HAS_TWILIO:
        return __virtualname__
    else:
        return False


def validate(config):
    '''
    Validate the beacon configuration
    '''
    # Configuration for twilio_txt_msg beacon should be a list of dicts
    if not isinstance(config, list):
        return False, ('Configuration for twilio_txt_msg beacon '
                       'must be a list.')
    else:
        _config = {}
        list(map(_config.update, config))

        if not all(x in _config for x in ('account_sid',
                                          'auth_token',
                                          'twilio_number')):
            return False, ('Configuration for twilio_txt_msg beacon '
                           'must contain account_sid, auth_token '
                           'and twilio_number items.')
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Emit a dict name "texts" whose value is a list
    of texts.

    .. code-block:: yaml

        beacons:
          twilio_txt_msg:
            - account_sid: "<account sid>"
            - auth_token: "<auth token>"
            - twilio_number: "+15555555555"
            - interval: 10

    '''
    log.trace('twilio_txt_msg beacon starting')

    _config = {}
    list(map(_config.update, config))

    ret = []
    if not all([_config['account_sid'],
                _config['auth_token'],
                _config['twilio_number']]):
        return ret
    output = {}
    output['texts'] = []
    client = TwilioRestClient(_config['account_sid'], _config['auth_token'])
    messages = client.messages.list(to=_config['twilio_number'])
    log.trace('Num messages: %d', len(messages))
    if len(messages) < 1:
        log.trace('Twilio beacon has no texts')
        return ret

    for message in messages:
        item = {}
        item['id'] = six.text_type(message.sid)
        item['body'] = six.text_type(message.body)
        item['from'] = six.text_type(message.from_)
        item['sent'] = six.text_type(message.date_sent)
        item['images'] = []

        if int(message.num_media):
            media = client.media(message.sid).list()
            if len(media):
                for pic in media:
                    item['images'].append(six.text_type(pic.uri))
        output['texts'].append(item)
        message.delete()
    ret.append(output)
    return ret
