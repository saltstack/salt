# -*- coding: utf-8 -*-
'''
Return salt data via Telegram.

The following fields can be set in the minion conf file::

    telegram.chat_id (required)
    telegram.token (required)

Telegram settings may also be configured as:

.. code-block:: yaml

    telegram:
      chat_id: 000000000
      token: 000000000:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

To use the Telegram return, append '--return telegram' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return telegram

'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import 3rd-party libs
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Import Salt Libs
import salt.returners

log = logging.getLogger(__name__)

__virtualname__ = 'telegram'


def __virtual__():
    '''
    Return virtual name of the module.

    :return: The virtual name of the module.
    '''
    if not HAS_REQUESTS:
        return False
    return __virtualname__


def _get_options(ret=None):
    '''
    Get the Telegram options from salt.

    :param ret:     The data to be sent.
    :return:        Dictionary containing the data and options needed to send
                    them to telegram.
    '''

    attrs = {'chat_id': 'chat_id',
            'token': 'token'}

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    log.debug('Options: {0}'.format(_options))
    return _options


def returner(ret):
    '''
    Send a Telegram message with the data.

    :param ret:     The data to be sent.
    :return:        Boolean if message was sent successfully.
    '''

    _options = _get_options(ret)

    chat_id = _options.get('chat_id')
    token = _options.get('token')

    if not chat_id:
        log.error('telegram.chat_id not defined in salt config')
    if not token:
        log.error('telegram.token not defined in salt config')

    returns = ret.get('return')

    message = ('id: {0}\r\n'
               'function: {1}\r\n'
               'function args: {2}\r\n'
               'jid: {3}\r\n'
               'return: {4}\r\n').format(
                    ret.get('id'),
                    ret.get('fun'),
                    ret.get('fun_args'),
                    ret.get('jid'),
                    returns)

    telegram = _post_message(chat_id,
                            message,
                            token)

    return telegram


def _post_message(chat_id, message, token):
    '''
    Send a message to a Telegram chat.

    :param chat_id:     The chat id.
    :param message:     The message to send to the telegram chat.
    :param token:       The Telegram API token.
    :return:            Boolean if message was sent successfully.
    '''

    url = 'https://api.telegram.org/bot{0}/sendMessage'.format(token)

    parameters = dict()
    if chat_id:
        parameters['chat_id'] = chat_id
    if message:
        parameters['text'] = message

    try:
        response = requests.post(
            url,
            data=parameters
        )
        result = response.json()

        log.debug(
            'Raw response of the telegram request is {0}'.format(response))

    except Exception:
        log.exception(
            'Sending telegram api request failed'
        )
        result = False

    if response and 'message_id' in result:
        success = True
    else:
        success = False

    log.debug('result {0}'.format(success))
    return bool(success)
