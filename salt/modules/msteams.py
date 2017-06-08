# -*- coding: utf-8 -*-
'''
Module for sending messages to MS Teams
.. versionadded:: Nitrogen
:configuration: This module can be used by either passing a hook_url
    directly or by specifying it in a configuration profile in the salt
    master/minion config.
    For example:
    .. code-block:: yaml
        msteams:
          hook_url: https://outlook.office.com/webhook/837
'''


# Import Python libs
from __future__ import absolute_import
import json
import logging

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
import salt.ext.six.moves.http_client

from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = 'msteams'


def __virtual__():
    '''
    Return virtual name of the module.
    :return: The virtual name of the module.
    '''
    return __virtualname__


def _get_hook_url():
    '''
    Return hook_url from minion/master config file
    or from pillar
    '''
    hook_url = __salt__['config.get']('msteams.hook_url') or \
        __salt__['config.get']('msteams:hook_url')

    if not hook_url:
        raise SaltInvocationError('No MS Teams hook_url found.')

    return hook_url


def post_card(message,
              hook_url=None,
              title=None,
              theme_color=None):
    '''
    Send a message to an MS Teams channel.
    :param message:     The message to send to the MS Teams channel.
    :param hook_url:    The Teams webhook URL, if not specified in the configuration.
    :param title:       Optional title for the posted card
    :param theme_color:  Optional hex color highlight for the posted card
    :return:            Boolean if message was sent successfully.
    CLI Example:
    .. code-block:: bash
        salt '*' msteams.post_card message="Build is done"
    '''

    if not hook_url:
        hook_url = _get_hook_url()

    if not message:
        log.error('message is a required option.')

    payload = {
        "text": message,
        "title": title,
        "themeColor": theme_color
    }

    result = salt.utils.http.query(hook_url, method='POST', data=json.dumps(payload), status=True)

    if result['status'] <= 201:
        return True
    else:
        return {
            'res': False,
            'message': result.get('body', result['status'])
        }
