# -*- coding: utf-8 -*-
'''
Beacon to emit Telegram messages

Requires the python-telegram-bot library

'''

# Import Python libs
from __future__ import absolute_import, unicode_literals
import logging
from salt.ext.six.moves import map

# Import 3rd Party libs
try:
    import telegram
    logging.getLogger('telegram').setLevel(logging.CRITICAL)
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

log = logging.getLogger(__name__)


__virtualname__ = 'telegram_bot_msg'


def __virtual__():
    if HAS_TELEGRAM:
        return __virtualname__
    else:
        return False


def validate(config):
    '''
    Validate the beacon configuration
    '''
    if not isinstance(config, list):
        return False, ('Configuration for telegram_bot_msg '
                       'beacon must be a list.')

    _config = {}
    list(map(_config.update, config))

    if not all(_config.get(required_config)
               for required_config in ['token', 'accept_from']):
        return False, ('Not all required configuration for '
                       'telegram_bot_msg are set.')

    if not isinstance(_config.get('accept_from'), list):
        return False, ('Configuration for telegram_bot_msg, '
                       'accept_from must be a list of usernames.')

    return True, 'Valid beacon configuration.'


def beacon(config):
    '''
    Emit a dict with a key "msgs" whose value is a list of messages
    sent to the configured bot by one of the allowed usernames.

    .. code-block:: yaml

        beacons:
          telegram_bot_msg:
            - token: "<bot access token>"
            - accept_from:
              - "<valid username>"
            - interval: 10

    '''

    _config = {}
    list(map(_config.update, config))

    log.debug('telegram_bot_msg beacon starting')
    ret = []
    output = {}
    output['msgs'] = []

    bot = telegram.Bot(_config['token'])
    updates = bot.get_updates(limit=100, timeout=0, network_delay=10)

    log.debug('Num updates: %d', len(updates))
    if not updates:
        log.debug('Telegram Bot beacon has no new messages')
        return ret

    latest_update_id = 0
    for update in updates:
        message = update.message

        if update.update_id > latest_update_id:
            latest_update_id = update.update_id

        if message.chat.username in _config['accept_from']:
            output['msgs'].append(message.to_dict())

    # mark in the server that previous messages are processed
    bot.get_updates(offset=latest_update_id + 1)

    log.debug('Emitting %d messages.', len(output['msgs']))
    if output['msgs']:
        ret.append(output)
    return ret
