# -*- coding: utf-8 -*-
'''
Return salt data via pushover (http://www.pushover.net)

.. versionadded:: Boron

The following fields can be set in the minion conf file::

    pushover.user (required)
    pushover.token (required)
    pushover.title (optional)
    pushover.device (optional)
    pushover.priority (optional)
    pushover.expire (optional)
    pushover.retry (optional)
    pushover.profile (optional)

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location::

    alternative.pushover.user
    alternative.pushover.token
    alternative.pushover.title
    alternative.pushover.device
    alternative.pushover.priority
    alternative.pushover.expire
    alternative.pushover.retry

PushOver settings may also be configured as::

    pushover:
        user: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        title: Salt Returner
        device: phone
        priority: -1
        expire: 3600
        retry: 5

    alternative.pushover:
        user: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        title: Salt Returner
        device: phone
        priority: 1
        expire: 4800
        retry: 2

    pushover_profile:
        token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

    pushover:
        user: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        profile: pushover_profile

    alternative.pushover:
        user: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        profile: pushover_profile

  To use the PushOver returner, append '--return pushover' to the salt command. ex:

  .. code-block:: bash

    salt '*' test.ping --return pushover

  To use the alternative configuration, append '--return_config alternative' to the salt command. ex:

    salt '*' test.ping --return pushover --return_config alternative
'''
from __future__ import absolute_import

# Import Python libs
import pprint
import logging
import urllib

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext.six.moves.urllib.parse import urljoin as _urljoin  # pylint: disable=import-error,no-name-in-module
import salt.ext.six.moves.http_client
# pylint: enable=import-error,no-name-in-module,redefined-builtin

# Import Salt Libs
import salt.returners
import salt.utils.http
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = 'pushover'


def _get_options(ret=None):
    '''
    Get the pushover options from salt.
    '''

    defaults = {'priority': '0'}

    attrs = {'pushover_profile': 'profile',
             'user': 'user',
             'device': 'device',
             'token': 'token',
             'priority': 'priority',
             'title': 'title',
             'api_version': 'api_version',
             'expire': 'expire',
             'retry': 'retry',
             'sound': 'sound',
             }

    profile_attr = 'pushover_profile'

    profile_attrs = {'user': 'user',
                     'device': 'device',
                     'token': 'token',
                     'priority': 'priority',
                     'title': 'title',
                     'api_version': 'api_version',
                     'expire': 'expire',
                     'retry': 'retry',
                     'sound': 'sound',
                     }

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   profile_attr=profile_attr,
                                                   profile_attrs=profile_attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__,
                                                   defaults=defaults)
    return _options


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
    if query_params is None:
        query_params = {}

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
            return ret
        except ValueError:
            ret['res'] = False
            ret['message'] = result
            return ret


def _validate_sound(sound,
                    token):
    '''
    Validate that the sound sent to Pushover exists.
    :param sound:       The sound that we want to verify
    :param token:       The PushOver token.
    '''
    res = {
            'message': 'Sound is invalid',
            'result': False
           }
    parameters = dict()
    parameters['token'] = token

    response = _query(function='validate_sound',
                      method='GET',
                      query_params=parameters)

    if response['res']:
        log.debug('response {0}'.format(response))
        if 'message' in response:
            _message = response.get('message', '')
            if 'status' in _message:
                if _message.get('dict', {}).get('status', '') == 1:
                    sounds = _message.get('dict', {}).get('sounds', '')
                    if sound in sounds:
                        res['result'] = True
                        res['message'] = 'Sound is valid.'
                else:
                    res['message'] = ''.join(_message.get('dict', {}).get('errors'))
    return res


def _validate_user(user,
                   device,
                   token):
    '''
    Validate that a Pushover user or group exists.
    :param user:        The user or group name, either will work.
    :param device:      The device for the user.
    :param token:       The PushOver token.
    '''
    ret = {
            'message': 'User key is invalid',
            'res': False
           }

    parameters = dict()
    parameters['user'] = user
    parameters['token'] = token
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
                    ret['res'] = True
                    ret['message'] = 'User key is valid.'
                else:
                    ret['res'] = False
                    ret['message'] = ''.join(_message.get('dict', {}).get('errors'))
    return ret


def _post_message(user,
                  device,
                  message,
                  title,
                  priority,
                  expire,
                  retry,
                  sound,
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

    user_validate = _validate_user(user, device, token)
    if not user_validate['res']:
        return user_validate

    parameters = dict()
    parameters['user'] = user
    parameters['device'] = device
    parameters['token'] = token
    parameters['title'] = title
    parameters['priority'] = priority
    parameters['expire'] = expire
    parameters['retry'] = retry
    parameters['message'] = message

    if sound:
        if _validate_sound(sound, token)['result']:
            parameters['sound'] = sound

    result = _query(function='message',
                    method='POST',
                    header_dict={'Content-Type': 'application/x-www-form-urlencoded'},
                    data=urllib.urlencode(parameters))

    return result


def returner(ret):
    '''
    Send an PushOver message with the data
    '''

    _options = _get_options(ret)

    user = _options.get('user')
    device = _options.get('device')
    token = _options.get('token')
    title = _options.get('title')
    priority = _options.get('priority')
    expire = _options.get('expire')
    retry = _options.get('retry')
    sound = _options.get('sound')

    if not token:
        raise SaltInvocationError('Pushover token is unavailable.')

    if not user:
        raise SaltInvocationError('Pushover user key is unavailable.')

    if priority and priority == 2:
        if not expire and not retry:
            raise SaltInvocationError('Priority 2 requires pushover.expire and pushover.retry options.')

    message = ('id: {0}\r\n'
               'function: {1}\r\n'
               'function args: {2}\r\n'
               'jid: {3}\r\n'
               'return: {4}\r\n').format(
                    ret.get('id'),
                    ret.get('fun'),
                    ret.get('fun_args'),
                    ret.get('jid'),
                    pprint.pformat(ret.get('return')))

    result = _post_message(user=user,
                           device=device,
                           message=message,
                           title=title,
                           priority=priority,
                           expire=expire,
                           retry=retry,
                           sound=sound,
                           token=token)

    if not result['res']:
        log.info('Error: {0}'.format(result['message']))
    return
