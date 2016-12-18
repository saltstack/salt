# -*- coding: utf-8 -*-
'''
Beacon to emit Telegram messages of a bot
'''

# Import Python libs
from __future__ import absolute_import
import logging

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


def __validate__(config):
    '''
    Validate the beacon configuration
    '''
    if not isinstance(config, dict):
        return False, ('Configuration for telegram_bot_msg '
                       'beacon must be a dictionary.')

    if not all(config.get(required_config)
               for required_config in ['token', 'accept_from']):
        return False, ('Not all required configuration for '
                       'telegram_bot_msg are set.')

    if not isinstance(config.get('accept_from'), list):
        return False, ('Configuration for telegram_bot_msg, '
                       'accept_from must be a list of usernames.')

    return True, 'Valid beacon configuration.'


def beacon(config):
    '''
    Emit a dict name "msgs" whose value is a list of messages sent to
    the configured bot by the listed users.

    .. code-block:: yaml

        beacons:
          telegram_bot_msg:
            token: "<bot access token>"
            accept_from:
              - <valid username>
            interval: 10

    '''
    log.debug('telegram_bot_msg beacon starting')
    ret = []
    output = {}
    output['msgs'] = []

    bot = telegram.Bot(config['token'])
    updates = bot.get_updates(limit=100, timeout=0, network_delay=10)

    log.debug('Num updates: {0}'.format(len(updates)))
    if len(updates) < 1:
        log.debug('Telegram Bot beacon has no new messages')
        return ret

    latest_update_id = 0
    for update in updates:
        message = update.message

        if update.update_id > latest_update_id:
            latest_update_id = update.update_id

        if message.chat.username in config['accept_from']:
            output['msgs'].append(message.to_dict())

    # mark in the server that previous messages are processed
    bot.get_updates(offset=latest_update_id + 1)

    log.debug('Emitting {0} messages.'.format(len(output['msgs'])))
    if len(output['msgs']) > 0:
        ret.append(output)
    return ret
