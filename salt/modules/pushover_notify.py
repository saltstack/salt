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

# Import 3rd-party libs
import requests
from requests.exceptions import ConnectionError
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext.six.moves.urllib.parse import urljoin as _urljoin
# pylint: enable=import-error,no-name-in-module

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
    headers = {}

    if query_params is None:
        query_params = {}

    if data is None:
        data = {}

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

    if not token:
        try:
            options = __salt__['config.option']('pushover')
            if not token:
                token = options.get('token')
        except (NameError, KeyError, AttributeError):
            log.error('No PushOver token found.')
            ret['message'] = 'No PushOver token found.'
            ret['res'] = False
            return ret

    api_url = 'https://api.pushover.net'
    base_url = _urljoin(api_url, api_version + '/')
    path = pushover_functions.get(function).get('request')
    url = _urljoin(base_url, path, False)

    try:
        result = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=query_params,
            data=data,
            verify=True,
        )
    except ConnectionError as e:
        ret['message'] = e
        ret['res'] = False
        return ret

    if result.status_code == 200:
        result = result.json()
        response = pushover_functions.get(function).get('response')
        if response in result and result[response] == 0:
            ret['res'] = False
        ret['message'] = result
        return ret
    else:
        try:
            result = result.json()
            if response in result and result[response] == 0:
                ret['res'] = False
            ret['message'] = result
            return ret
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
    parameters = dict()
    parameters['token'] = token

    response = _query(function='validate_sound',
                      method='GET',
                      query_params=parameters)

    if response['res']:
        if 'message' in response:
            if 'status' in response['message']:
                if response['message']['status'] == 1:
                    sounds = response['message']['sounds']
                    if sound in sounds:
                        return True
                    else:
                        log.info('Warning: {0} not a valid sound.'.format(sound))
                        return False
                else:
                    log.info('Error: {0}'.format(''.join(response['message']['errors'])))
    return False


def _validate_user(user,
                   device,
                   token):
    '''
    Send a message to a Pushover user or group.
    :param user:        The user or group name, either will work.
    :param device:      The device for the user.
    :param token:       The PushOver token.
    '''
    parameters = dict()
    parameters['user'] = user
    parameters['token'] = token
    parameters['device'] = device

    response = _query(function='validate_user',
                      method='POST',
                      data=parameters)

    if response['res']:
        if 'message' in response:
            if 'status' in response['message']:
                if response['message']['status'] == 1:
                    return True
                else:
                    log.info('Error: {0}'.format(''.join(response['message']['errors'])))
    return False


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
    :param priority     The priority of the message, defaults to 0.
    :param api_version: The PushOver API version, if not specified in the configuration.
    :param notify:      Whether to notify the room, default: False.
    :param token:       The PushOver token, if not specified in the configuration.
    :return:            Boolean if message was sent successfully.
    '''

    if not token:
        log.error('token is a required argument.')

    if not user:
        log.error('user is a required argument.')

    if not message:
        log.error('message is a required argument.')

    if not _validate_user(user, device, token):
        return

    parameters = dict()
    parameters['user'] = user
    parameters['device'] = device
    parameters['token'] = token
    parameters['title'] = title
    parameters['priority'] = priority
    parameters['expire'] = expire
    parameters['retry'] = retry
    parameters['message'] = message

    if sound and _validate_sound(sound, token):
        parameters['sound'] = sound

    result = _query(function='message',
                    method='POST',
                    data=parameters)

    if result['res']:
        return True
    else:
        return result
