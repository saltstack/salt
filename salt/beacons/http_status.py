# -*- coding: utf-8 -*-
'''
Beacon to manage and report the status of a server status endpoint.
Fire an event when specified values don't match returned response.

'''

# Import Python libs
from __future__ import absolute_import, unicode_literals
import logging
import operator
import re
import requests
import itertools
import salt.utils.data
from salt.ext.six.moves import map

log = logging.getLogger(__name__)

__virtualname__ = 'http_status'

comparisons = {
    '==': operator.eq,
    '<': operator.lt,
    '>': operator.gt,
    '<=': operator.le,
    '>=': operator.ge,
    '!=': operator.ne,
    'search': re.search
}

attr_func_map = {
  'status': lambda x: x.status_code,
  'content': lambda x: x.json()
}

required_site_attributes = {'url'}
optional_site_attributes = {'content', 'status'}


def __virtual__():
    return __virtualname__


def validate(config):
    '''
    Validate the beacon configuration
    '''
    valid = True
    messages = []

    if not isinstance(config, list):
        valid = False
        messages.append('[-] Configuration for %s beacon must be a list', config)
    else:
        _config = {}
        list(map(_config.update, config))

    try:
        sites = _config.get('sites', {})
    except AttributeError:
        valid = False
        messages.append('[-] Sites for %s beacon must be a dict', __virtualname__)

    if not sites:
        valid = False
        messages.append('[-] Configuration does not contain sites')

    for site, settings in sites.items():
        if required_site_attributes.isdisjoint(set(settings.keys())):
            valid = False
            messages.append('[-] Sites for {} beacon requires {}'.format(__virtualname__,
                                                                         required_site_attributes))
        log.debug('[+] site: %s', site)
        log.debug('[+] settings: %s', settings)

        for optional_attrs in itertools.chain(settings.get(attr, []) for attr in optional_site_attributes):
            for item in optional_attrs:
                cmp = item.get('comp')
                if cmp and cmp not in comparisons:
                    valid = False
                    messages.append('[-] Invalid comparison operator %s', cmp)

    messages.append('[+] Valid beacon configuration')
    return valid, messages


def beacon(config):
    '''
    Check on different service status reported by the django-server-status
    library.

    .. code-block:: yaml

        beacons:
          http_status:
            - sites:
                example-site-1:
                  url: "https://example.com/status"
                  timeout: 30
                  content-type: json
                  status:
                    - value: 400
                      comp: <
                    - value: 300
                      comp: '>='
                  content:
                    - path: 'certificate:status'
                      value: down
                      comp: '=='
                    - path: 'status_all'
                      value: down
                      comp: '=='
            - interval: 10
    '''
    ret = []

    _config = {}
    list(map(_config.update, config))

    for site, site_config in _config.get('sites', {}).items():
        url = site_config.pop('url')
        content_type = site_config.pop('content_type', 'json')
        try:
            r = requests.get(url, timeout=site_config.pop('timeout', 30))
        except requests.exceptions.RequestException as e:
            log.info("Request failed: %s", e)
            if r.raise_for_status:
                log.info('[-] Response from status endpoint was invalid: '
                         '%s', r.status_code)
                _failed = {'status_code': r.status_code,
                           'url': url}
                ret.append(_failed)
                continue

        for attr, checks in site_config.items():
            for check in checks:
                log.debug('[+] response_item: %s', attr)
                attr_path = check.get('path', '')
                comp = comparisons[check['comp']]
                expected_value = check['value']
                if attr_path:
                    received_value = salt.utils.data.traverse_dict_and_list(attr_func_map[attr](r), attr_path)
                else:
                    received_value = attr_func_map[attr](r)
                if received_value is None:
                    log.info('[-] No data found at location %s for url %s', attr_path, url)
                    continue
                log.debug('[+] expected_value: %s', expected_value)
                log.debug('[+] received_value: %s', received_value)
                if not comp(expected_value, received_value):
                    _failed = {'expected': expected_value,
                               'received': received_value,
                               'url': url,
                               'path': attr_path
                               }
                    ret.append(_failed)
    return ret
