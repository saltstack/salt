# -*- coding: utf-8 -*-
'''
Module for sending messages to Pushover (https://www.pushover.net)

.. versionadded:: Boron

:configuration: This module can be used by either passing an api key and version
    directly or by specifying both in a configuration profile in the salt
    master/minion config.

    For example:

    .. code-block:: yaml

        pushover:
          token: abAHuZyCLtdH8P4zhmFZmgUHUsv1ei8
'''

# Import Python libs
from __future__ import absolute_import
import logging
import urllib

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext.six.moves.urllib.parse import urljoin as _urljoin
import salt.ext.six.moves.http_client
# pylint: enable=import-error,no-name-in-module,redefined-builtin

# Import salt libs
from salt.exceptions import SaltInvocationError
import salt.utils.http

log = logging.getLogger(__name__)
__virtualname__ = 'pushover'


def __virtual__():
    '''
    Return virtual name of the module.

    :return: The virtual name of the module.
    '''
    return __virtualname__


def _query(function,
           token=None,
           api_version='1',
           method='POST',
           header_dict=None,
           data=None,
           query_params=None):
    '''
    PushOver object method function to construct and execute on the API URL.

    :param token:       The PushOver api key.
    :param api_version: The PushOver API version to use, defaults to version 1.
    :param function:    The PushOver api function to perform.
    :param method:      The HTTP method, e.g. GET or POST.
    :param data:        The data to be sent for POST method.
    :return:            The json response from the API call or False.
    '''

    ret = {'message': '',
           'res': True}

    pushover_functions = {
        'message': {
            'request': 'messages.json',
            'response': 'status',
        },
        'validate_user': {
            'request': 'users/validate.json',
            'response': 'status',
        },
        'validate_sound': {
            'request': 'sounds.json',
            'response': 'status',
        },
    }

    api_url = 'https://api.pushover.net'
    base_url = _urljoin(api_url, api_version + '/')
    path = pushover_functions.get(function).get('request')
    url = _urljoin(base_url, path, False)

    if not query_params:
        query_params = {}

    decode = True
    if method == 'DELETE':
        decode = False

    result = salt.utils.http.query(
        url,
        method,
        params=query_params,
        data=data,
        header_dict=header_dict,
        decode=decode,
        decode_type='json',
        text=True,
        status=True,
        cookies=True,
        persist_session=True,
        opts=__opts__,
    )

    if result.get('status', None) == salt.ext.six.moves.http_client.OK:
        response = pushover_functions.get(function).get('response')
        if response in result and result[response] == 0:
            ret['res'] = False
        ret['message'] = result
        return ret
    else:
        try:
            if 'response' in result and result[response] == 0:
                ret['res'] = False
            ret['message'] = result
        except ValueError:
            ret['res'] = False
            ret['message'] = result
        return ret


def _validate_sound(sound,
                    token):
    '''
    Send a message to a Pushover user or group.
    :param sound:       The sound that we want to verify
    :param token:       The PushOver token.
    '''
    ret = {
            'message': 'Sound is invalid',
            'res': False
           }
    parameters = dict()
    parameters['token'] = token

    response = _query(function='validate_sound',
                      method='GET',
                      query_params=parameters)

    if response['res']:
        if 'message' in response:
            _message = response.get('message', '')
            if 'status' in _message:
                if _message.get('dict', {}).get('status', '') == 1:
                    sounds = _message.get('dict', {}).get('sounds', '')
                    if sound in sounds:
                        ret['message'] = 'Valid sound {0}.'.format(sound)
                        ret['res'] = True
                    else:
                        ret['message'] = 'Warning: {0} not a valid sound.'.format(sound)
                        ret['res'] = False
                else:
                    ret['message'] = ''.join(_message.get('dict', {}).get('errors'))
    return ret


def _validate_user(user,
                   device,
                   token):
    '''
    Send a message to a Pushover user or group.
    :param user:        The user or group name, either will work.
    :param device:      The device for the user.
    :param token:       The PushOver token.
    '''
    res = {
            'message': 'User key is invalid',
            'result': False
           }

    parameters = dict()
    parameters['user'] = user
    parameters['token'] = token
    if device:
        parameters['device'] = device

    response = _query(function='validate_user',
                      method='POST',
                      header_dict={'Content-Type': 'application/x-www-form-urlencoded'},
                      data=urllib.urlencode(parameters))

    if response['res']:
        if 'message' in response:
            _message = response.get('message', '')
            if 'status' in _message:
                if _message.get('dict', {}).get('status', None) == 1:
                    res['result'] = True
                    res['message'] = 'User key is valid.'
                else:
                    res['result'] = False
                    res['message'] = ''.join(_message.get('dict', {}).get('errors'))
    return res


def post_message(user=None,
                 device=None,
                 message=None,
                 title=None,
                 priority=None,
                 expire=None,
                 retry=None,
                 sound=None,
                 api_version=1,
                 token=None):
    '''
    Send a message to a Pushover user or group.

    :param user:        The user or group to send to, must be key of user or group not email address.
    :param message:     The message to send to the PushOver user or group.
    :param title:       Specify who the message is from.
    :param priority:    The priority of the message, defaults to 0.
    :param expire:      The message should expire after N number of seconds.
    :param retry:       The number of times the message should be retried.
    :param sound:       The sound to associate with the message.
    :param api_version: The PushOver API version, if not specified in the configuration.
    :param token:       The PushOver token, if not specified in the configuration.
    :return:            Boolean if message was sent successfully.

    CLI Example:

    .. code-block:: bash

        salt '*' pushover.post_message user='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' title='Message from Salt' message='Build is done'

        salt '*' pushover.post_message user='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' title='Message from Salt' message='Build is done' priority='2' expire='720' retry='5'

    '''

    if not token:
        token = __salt__['config.get']('pushover.token') or \
                __salt__['config.get']('pushover:token')
        if not token:
            raise SaltInvocationError('Pushover token is unavailable.')

    if not user:
        user = __salt__['config.get']('pushover.user') or \
               __salt__['config.get']('pushover:user')
        if not user:
            raise SaltInvocationError('Pushover user key is unavailable.')

    if not message:
        raise SaltInvocationError('Required parameter "message" is missing.')

    user_validate = _validate_user(user, device, token)
    if not user_validate['result']:
        return user_validate

    if not title:
        title = 'Message from SaltStack'

    parameters = dict()
    parameters['user'] = user
    parameters['device'] = device
    parameters['token'] = token
    parameters['title'] = title
    parameters['priority'] = priority
    parameters['expire'] = expire
    parameters['retry'] = retry
    parameters['message'] = message

    if sound and _validate_sound(sound, token)['res']:
        parameters['sound'] = sound

    result = _query(function='message',
                    method='POST',
                    header_dict={'Content-Type': 'application/x-www-form-urlencoded'},
                    data=urllib.urlencode(parameters))

    if result['res']:
        return True
    else:
        return result
