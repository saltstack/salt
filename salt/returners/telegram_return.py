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
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging

# Import Salt Libs
import salt.returners

log = logging.getLogger(__name__)

__virtualname__ = 'telegram'


def __virtual__():
    '''
    Return virtual name of the module.

    :return: The virtual name of the module.
    '''
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
    log.debug('Options: %s', _options)
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

    return __salt__['telegram.post_message'](message,
                                             chat_id=chat_id,
                                             token=token)
