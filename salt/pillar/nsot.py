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

fqdn_separator: ``str``
    This is in case a minion_id contains a dot. Because NSoT
    doesn't allow hostnmes with dots, this option allows you to look up a device
    with this character replacing dots. For example, with this option set to
    '-', the minion rtr1.lax1 would be looked up in NSoT as rtr1-lax1.

all_devices_regex: ``list``
    This is a list of minions that will receive all device
    information in NSoT, given in the form of regular expressions. These minions
    do not need to be in nsot in order to retrieve all device info from nsot.

minion_regex: ``list``
    This is in case you only want certain minions being looked
    up in NSoT. For example, if you have 500 minions on a single master, you may
    not want all of them hitting the NSoT endpoint. With this list of regular
    expressions, only minions that match will be queried. This is
    assumed to be a network device that exists in nsot.

Here's an example config with all options:

.. code-block:: yaml

    ext_pillar:
      - nsot:
        api_url: http://nsot_url.com/api/
        email: 'user@site.com'
        secret_key: abc234
        fqdn_separator: '-'
        all_devices_regex:
          - 'server*'
          - '^cent*'
        minion_regex:
          - 'rtr*'
          - 'sw*'
          - '^router*'

'''

from __future__ import absolute_import, print_function, unicode_literals
import logging
import re
try:
    import urlparse
except ImportError:
    from urllib import parse as urlparse

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
    url = urlparse.urljoin(url, 'authenticate')
    data_dict = {"email": email, "secret_key": secret_key}
    query = salt.utils.http.query(url, data=data_dict, method='POST',
                                  decode=True)
    error = query.get('error')
    if error:
        log.error('Cannot obtain NSoT authentication token due to: %s.', error)
        log.debug('Please verify NSoT URL %s is reachable and email %s is valid', url, email)
        return False
    else:
        log.debug('successfully obtained token from nsot!')
        return query['dict'].get('auth_token')


def _check_regex(minion_id, regex):
    '''
    check whether or not this minion should have this external pillar returned

    :param minion_id: str
    :param minion_regex: list
    :return: bool
    '''
    get_pillar = False
    for pattern in regex:
        log.debug('nsot external pillar comparing %s with %s', minion_id, regex)
        match = re.search(pattern, minion_id)
        if match and match.string == minion_id:
            log.debug('nsot external pillar found a match!')
            get_pillar = True
            break
        log.debug('nsot external pillar unable to find a match!')
    return get_pillar


def _query_nsot(url, headers, device=None):
    '''
    if a device is given, query nsot for that specific device, otherwise return
    all devices

    :param url: str
    :param headers: dict
    :param device: None or str
    :return:
    '''
    url = urlparse.urljoin(url, 'devices')
    ret = {}
    if not device:
        query = salt.utils.http.query(url, header_dict=headers, decode=True)
    else:
        url = urlparse.urljoin(url, device)
        query = salt.utils.http.query(url, header_dict=headers,
                                      decode=True)
    error = query.get('error')
    if error:
        log.error('can\'t get device(s) from nsot! reason: %s', error)
    else:
        ret = query['dict']

    return ret


def _proxy_info(minion_id, api_url, email, secret_key, fqdn_separator):
    '''
    retrieve a dict of a device that exists in nsot

    :param minion_id: str
    :param api_url: str
    :param email: str
    :param secret_key: str
    :param fqdn_separator: str
    :return: dict
    '''
    device_info = {}
    if fqdn_separator:
        minion_id = minion_id.replace('.', fqdn_separator)
    token = _get_token(api_url, email, secret_key)
    if token:
        headers = {'Authorization': 'AuthToken {}:{}'.format(email, token)}
        device_info = _query_nsot(api_url, headers, device=minion_id)

    return device_info


def _all_nsot_devices(api_url, email, secret_key):
    '''
    retrieve a list of all devices that exist in nsot

    :param api_url: str
    :param email: str
    :param secret_key: str
    :return: dict
    '''
    token = _get_token(api_url, email, secret_key)
    all_devices = {}
    if token:
        headers = {'Authorization': 'AuthToken {}:{}'.format(email, token)}
        all_devices = _query_nsot(api_url, headers)

    return all_devices


def ext_pillar(minion_id,
               pillar,
               api_url,
               email,
               secret_key,
               fqdn_separator=None,
               all_devices_regex=None,
               minion_regex=None):
    '''
    Query NSoT API for network devices
    '''
    ret = {}
    if minion_id == '*':
        log.info('There\'s no data to collect from NSoT for the Master')
        return ret

    if minion_regex:
        get_ext_pillar = _check_regex(minion_id, minion_regex)
        if get_ext_pillar:
            ret['nsot'] = _proxy_info(minion_id,
                                      api_url,
                                      email,
                                      secret_key,
                                      fqdn_separator)

    if all_devices_regex:
        get_ext_pillar = _check_regex(minion_id, all_devices_regex)
        if get_ext_pillar:
            if not ret.get('nsot'):
                ret['nsot'] = {}
            ret['nsot']['devices'] = _all_nsot_devices(api_url,
                                                       email,
                                                       secret_key)

    return ret
