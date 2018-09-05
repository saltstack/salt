# -*- coding: utf-8 -*-
'''
A module that adds data to the Pillar structure from the NSoT API.

.. versionadded:: Neon

Configuring the NSoT ext_pillar
---------------------------------

The following fields are required:

.. code-block:: yaml

    ext_pillar:
      - nsot:
        api_url: http://nsot_url.com/api/
        email: 'user@site.com'
        secret_key: abc123

.. note::

    Note the trailing slash on the api_url field. Although NSoT gives the option
    of whether or not to use the tailing slash, this module assumes that the
    APPEND_SLASH option is set to True (the default)

The following fields are optional:

replace_dot: ``str``
    This is in case a minion_id contains a dot. Because NSoT
    doesn't allow hostnmes with dots, this option allows you to look up a device
    with this character replacing dots. For example, with this option set to
     '-', the minion rtr1.lax1 would be looked up in NSoT as rtr1-lax1.

all_device_info: ``list``
    This is a list of minions that will receive all device
    information in NSoT. For example, if this list contained the entry
    'test_min', then the minion 'test_min' would have all devices in NSoT under
    pillar['nsot']['devices']

minion_regex: ``list``
    This is in case you only want certain minions being looked
    up in NSoT. For example, if you have 500 minions on a single master, you may
    not want all of them hitting the NSoT endpoint. With this list of regexes,
    only minions matching the regex will be queried.

Here's an example config with all options:

.. code-block:: yaml

    ext_pillar:
      - nsot:
        api_url: http://nsot_url.com/api/
        email: 'user@site.com'
        secret_key: abc234
        replace_dot: '-'
        all_device_info:
          - minion_1
          - minion_2
        minion_regex:
          - 'rtr*'
          - 'sw*'
          - '^router*'

'''

from __future__ import absolute_import, print_function, unicode_literals
import logging
import re

# Import Salt libs
import salt.utils.http

log = logging.getLogger(__name__)


def _get_token(url, email, secret_key):
    '''
    retrieve the auth_token from nsot

    :param url: str
    :param email: str
    :param secret_key: str
    :return: str
    '''
    url += 'authenticate/'
    data_dict = {"email": email, "secret_key": secret_key}
    query = salt.utils.http.query(url, data=data_dict, method='POST',
                                  decode=True)
    error = query.get('error')
    if error:
        log.error('can\'t get auth_token from nsot! reason: %s', error)
        return False
    else:
        log.debug('successfully obtained token from nsot!')
        return query['dict']['auth_token']


def _check_minion_regex(minion_id, minion_regex):
    '''
    check whether or not this minion should have this external pillar returned

    :param minion_id: str
    :param minion_regex: list
    :return: bool
    '''
    get_pillar = False
    for pattern in minion_regex:
        log.debug('searching %s using %s', minion_id, minion_regex)
        match = re.search(pattern, minion_id)
        if match and match.string == minion_id:
            log.debug('found match! %s: regex %s', minion_id, minion_regex)
            get_pillar = True
            break
        log.debug('unable to match %s using regex %s', minion_id, minion_regex)
    return get_pillar


def _query_nsot(url, headers, device=None):
    url += 'devices/'
    if not device:
        query = salt.utils.http.query(url, header_dict=headers, decode=True)
    else:
        device += '/'
        query = salt.utils.http.query(url + device, header_dict=headers,
                                      decode=True)
    error = query.get('error')
    if error:
        log.error('can\'t get device(s) from nsot! reason: %s', error)
        return {}
    else:
        return query['dict']


def ext_pillar(minion_id,
               pillar,
               api_url,
               email,
               secret_key,
               replace_dot=None,
               all_device_info=None,
               minion_regex=None):
    '''
    Query NSoT API for network devices
    '''
    ret = {}
    if minion_id == '*':
        log.info('There\'s no data to collect from NSoT for the Master')
        return ret

    if minion_regex:
        get_ext_pillar = _check_minion_regex(minion_id, minion_regex)
        if not get_ext_pillar:
            if all_device_info:
                if minion_id not in all_device_info:
                    return ret
            else:
                return ret

    token = _get_token(api_url, email, secret_key)

    if not token:
        return ret

    headers = {'Authorization': 'AuthToken {}:{}'.format(email, token)}

    if all_device_info:
        if minion_id in all_device_info:
            all_devices = _query_nsot(api_url, headers)
            if all_devices:
                ret['nsot'] = {}
                ret['nsot']['devices'] = all_devices
            return ret

    if replace_dot:
        minion_id = minion_id.replace('.', replace_dot)

    device_info = _query_nsot(api_url, headers, device=minion_id)
    if device_info:
        ret['nsot'] = device_info

    return ret
