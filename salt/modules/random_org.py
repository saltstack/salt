# -*- coding: utf-8 -*-
'''
Module for retrieving random information from Random.org

.. versionadded:: 2015.5.0

:configuration: This module can be used by either passing an api key and version
    directly or by specifying both in a configuration profile in the salt
    master/minion config.

    For example:

    .. code-block:: yaml

        random_org:
          api_key: 7be1402d-5719-5bd3-a306-3def9f135da5
          api_version: 1
'''

# Import Python libs
from __future__ import absolute_import
import logging

# Import 3rd-party libs
import json
from requests.exceptions import ConnectionError
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext.six.moves.urllib.parse import urljoin as _urljoin

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
# pylint: enable=import-error,no-name-in-module

log = logging.getLogger(__name__)
__virtualname__ = 'random_org'

RANDOM_ORG_FUNCTIONS = {
    '1': {
        'getUsage': {
            'method': 'getUsage',
        },
        'generateIntegers': {
            'method': 'generateIntegers',
        },
        'generateStrings': {
            'method': 'generateStrings',
        },
        'generateUUIDs': {
            'method': 'generateUUIDs',
        },
        'generateDecimalFractions': {
            'method': 'generateDecimalFractions',
        },
        'generateGaussians': {
            'method': 'generateGaussians',
        },
        'generateBlobs': {
            'method': 'generateBlobs',
        },
    }
}


def __virtual__():
    '''
    Return virtual name of the module.

    :return: The virtual name of the module.
    '''
    if not HAS_REQUESTS:
        return False

    return __virtualname__


def _query(api_version=None, data=None):
    '''
    Slack object method function to construct and execute on the API URL.

    :param api_key:     The Random.org api key.
    :param api_version: The version of Random.org api.
    :param data:        The data to be sent for POST method.
    :return:            The json response from the API call or False.
    '''

    if data is None:
        data = {}

    ret = {'res': True}

    api_url = 'https://api.random.org/'
    base_url = _urljoin(api_url, 'json-rpc/' + str(api_version) + '/invoke')

    data = json.dumps(data)

    try:
        result = requests.request(
            method='POST',
            url=base_url,
            headers={},
            params={},
            data=data,
            verify=True,
        )
    except ConnectionError as e:
        ret['message'] = e
        ret['res'] = False
        return ret

    if result.status_code == 200:
        result = result.json()
        if result.get('result'):
            return result.get('result')
        if result.get('error'):
            return result.get('error')
        return ret
    elif result.status_code == 204:
        return True
    else:
        ret['message'] = result.text
        return ret


def getUsage(api_key=None, api_version=None):
    '''
    Show current usages statistics

    :param api_key: The Random.org api key.
    :param api_version: The Random.org api version.
    :return: The current usage statistics.

    CLI Example:

    .. code-block:: bash

        salt '*' random_org.getUsage

        salt '*' random_org.getUsage api_key=peWcBiMOS9HrZG15peWcBiMOS9HrZG15 api_version=1
    '''
    ret = {'res': True}

    if not api_key or not api_version:
        try:
            options = __salt__['config.option']('random_org')
            if not api_key:
                api_key = options.get('api_key')
            if not api_version:
                api_version = options.get('api_version')
        except (NameError, KeyError, AttributeError):
            log.error('No Random.org api key found.')
            ret['message'] = 'No Random.org api key or api version found.'
            ret['res'] = False
            return ret

    if isinstance(api_version, int):
        api_version = str(api_version)

    _function = RANDOM_ORG_FUNCTIONS.get(api_version).get('getUsage').get('method')
    data = {}
    data['id'] = 1911220
    data['jsonrpc'] = '2.0'
    data['method'] = _function
    data['params'] = {'apiKey': api_key}

    result = _query(api_version=api_version, data=data)

    if result:
        ret['bitsLeft'] = result.get('bitsLeft')
        ret['requestsLeft'] = result.get('requestsLeft')
        ret['totalBits'] = result.get('totalBits')
        ret['totalRequests'] = result.get('totalRequests')
    else:
        ret['res'] = False
        ret['message'] = result['message']
    return ret


def generateIntegers(api_key=None,
                     api_version=None,
                     **kwargs):
    '''
    Generate random integers

    :param api_key: The Random.org api key.
    :param api_version: The Random.org api version.
    :param number: The number of integers to generate
    :param minimum: The lower boundary for the range from which the
                    random numbers will be picked. Must be within
                    the [-1e9,1e9] range.
    :param maximum: The upper boundary for the range from which the
                    random numbers will be picked. Must be within
                    the [-1e9,1e9] range.
    :param replacement: Specifies whether the random numbers should
                        be picked with replacement. The default (true)
                        will cause the numbers to be picked with replacement,
                        i.e., the resulting numbers may contain duplicate
                        values (like a series of dice rolls). If you want the
                        numbers picked to be unique (like raffle tickets drawn
                        from a container), set this value to false.
    :param base: Specifies the base that will be used to display the numbers.
                 Values allowed are 2, 8, 10 and 16. This affects the JSON
                 types and formatting of the resulting data as discussed below.
    :return: A list of integers.

    CLI Example:

    .. code-block:: bash

        salt '*' random_org.generateIntegers number=5 minimum=1 maximum=6

        salt '*' random_org.generateIntegers number=5 minimum=2 maximum=255 base=2

    '''
    ret = {'res': True}

    if not api_key or not api_version:
        try:
            options = __salt__['config.option']('random_org')
            if not api_key:
                api_key = options.get('api_key')
            if not api_version:
                api_version = options.get('api_version')
        except (NameError, KeyError, AttributeError):
            log.error('No Random.org api key found.')
            ret['message'] = 'No Random.org api key or api version found.'
            ret['res'] = False
            return ret

    for item in ['number', 'minimum', 'maximum']:
        if item not in kwargs:
            ret['res'] = False
            ret['message'] = 'Rquired argument, {0} is missing.'.format(item)
            return ret

    if not 1 <= kwargs['number'] <= 10000:
        ret['res'] = False
        ret['message'] = 'Number of integers must be between 1 and 10000'
        return ret

    if not -1000000000 <= kwargs['minimum'] <= 1000000000:
        ret['res'] = False
        ret['message'] = 'Minimum argument must be between -1,000,000,000 and 1,000,000,000'
        return ret

    if not -1000000000 <= kwargs['maximum'] <= 1000000000:
        ret['res'] = False
        ret['message'] = 'Maximum argument must be between -1,000,000,000 and 1,000,000,000'
        return ret

    if 'base' in kwargs:
        base = kwargs['base']
        if base not in [2, 8, 10, 16]:
            ret['res'] = False
            ret['message'] = 'Base must be either 2, 8, 10 or 16.'
            return ret
    else:
        base = 10

    if 'replacement' not in kwargs:
        replacement = True
    else:
        replacement = kwargs['replacement']

    if isinstance(api_version, int):
        api_version = str(api_version)

    _function = RANDOM_ORG_FUNCTIONS.get(api_version).get('generateIntegers').get('method')
    data = {}
    data['id'] = 1911220
    data['jsonrpc'] = '2.0'
    data['method'] = _function
    data['params'] = {'apiKey': api_key,
                      'n': kwargs['number'],
                      'min': kwargs['minimum'],
                      'max': kwargs['maximum'],
                      'replacement': replacement,
                      'base': base
                      }

    result = _query(api_version=api_version, data=data)
    if result:
        log.debug('result {0}'.format(result))
        if 'random' in result:
            random_data = result.get('random').get('data')
            ret['data'] = random_data
        else:
            ret['res'] = False
            ret['message'] = result['message']
    else:
        ret['res'] = False
        ret['message'] = result['message']
    return ret


def generateStrings(api_key=None,
                    api_version=None,
                    **kwargs):
    '''
    Generate random strings.

    :param api_key: The Random.org api key.
    :param api_version: The Random.org api version.
    :param number: The number of strings to generate.
    :param length: The length of each string. Must be
                   within the [1,20] range. All strings
                   will be of the same length
    :param characters: A string that contains the set of
                       characters that are allowed to occur
                       in the random strings. The maximum number
                       of characters is 80.
    :param replacement: Specifies whether the random strings should be picked
                        with replacement. The default (true) will cause the
                        strings to be picked with replacement, i.e., the
                        resulting list of strings may contain duplicates (like
                        a series of dice rolls). If you want the strings to be
                        unique (like raffle tickets drawn from a container), set
                        this value to false.
    :return: A list of strings.

    CLI Example:

    .. code-block:: bash

        salt '*' random_org.generateStrings number=5 length=8 characters='abcdefghijklmnopqrstuvwxyz'

        salt '*' random_org.generateStrings number=10 length=16 characters'abcdefghijklmnopqrstuvwxyz'

    '''
    ret = {'res': True}

    if not api_key or not api_version:
        try:
            options = __salt__['config.option']('random_org')
            if not api_key:
                api_key = options.get('api_key')
            if not api_version:
                api_version = options.get('api_version')
        except (NameError, KeyError, AttributeError):
            log.error('No Random.org api key found.')
            ret['message'] = 'No Random.org api key or api version found.'
            ret['res'] = False
            return ret

    for item in ['number', 'length', 'characters']:
        if item not in kwargs:
            ret['res'] = False
            ret['message'] = 'Required argument, {0} is missing.'.format(item)
            return ret

    if not 1 <= kwargs['number'] <= 10000:
        ret['res'] = False
        ret['message'] = 'Number of strings must be between 1 and 10000'
        return ret

    if not 1 <= kwargs['length'] <= 20:
        ret['res'] = False
        ret['message'] = 'Length of strings must be between 1 and 20'
        return ret

    if len(kwargs['characters']) >= 80:
        ret['res'] = False
        ret['message'] = 'Length of characters must be less than 80.'
        return ret

    if isinstance(api_version, int):
        api_version = str(api_version)

    if 'replacement' not in kwargs:
        replacement = True
    else:
        replacement = kwargs['replacement']

    _function = RANDOM_ORG_FUNCTIONS.get(api_version).get('generateStrings').get('method')
    data = {}
    data['id'] = 1911220
    data['jsonrpc'] = '2.0'
    data['method'] = _function
    data['params'] = {'apiKey': api_key,
                      'n': kwargs['number'],
                      'length': kwargs['length'],
                      'characters': kwargs['characters'],
                      'replacement': replacement,
                      }

    result = _query(api_version=api_version, data=data)
    if result:
        if 'random' in result:
            random_data = result.get('random').get('data')
            ret['data'] = random_data
        else:
            ret['res'] = False
            ret['message'] = result['message']
    else:
        ret['res'] = False
        ret['message'] = result['message']
    return ret


def generateUUIDs(api_key=None,
                  api_version=None,
                  **kwargs):
    '''
    Generate a list of random UUIDs

    :param api_key: The Random.org api key.
    :param api_version: The Random.org api version.
    :param number: How many random UUIDs you need.
                   Must be within the [1,1e3] range.
    :return: A list of UUIDs

    CLI Example:

    .. code-block:: bash

        salt '*' random_org.generateUUIDs number=5

    '''
    ret = {'res': True}

    if not api_key or not api_version:
        try:
            options = __salt__['config.option']('random_org')
            if not api_key:
                api_key = options.get('api_key')
            if not api_version:
                api_version = options.get('api_version')
        except (NameError, KeyError, AttributeError):
            log.error('No Random.org api key found.')
            ret['message'] = 'No Random.org api key or api version found.'
            ret['res'] = False
            return ret

    for item in ['number']:
        if item not in kwargs:
            ret['res'] = False
            ret['message'] = 'Required argument, {0} is missing.'.format(item)
            return ret

    if isinstance(api_version, int):
        api_version = str(api_version)

    if not 1 <= kwargs['number'] <= 1000:
        ret['res'] = False
        ret['message'] = 'Number of UUIDs must be between 1 and 1000'
        return ret

    _function = RANDOM_ORG_FUNCTIONS.get(api_version).get('generateUUIDs').get('method')
    data = {}
    data['id'] = 1911220
    data['jsonrpc'] = '2.0'
    data['method'] = _function
    data['params'] = {'apiKey': api_key,
                      'n': kwargs['number'],
                      }

    result = _query(api_version=api_version, data=data)
    if result:
        if 'random' in result:
            random_data = result.get('random').get('data')
            ret['data'] = random_data
        else:
            ret['res'] = False
            ret['message'] = result['message']
    else:
        ret['res'] = False
        ret['message'] = result['message']
    return ret


def generateDecimalFractions(api_key=None,
                             api_version=None,
                             **kwargs):
    '''
    Generates true random decimal fractions

    :param api_key: The Random.org api key.
    :param api_version: The Random.org api version.
    :param number: How many random decimal fractions
                   you need. Must be within the [1,1e4] range.
    :param decimalPlaces: The number of decimal places
                          to use. Must be within the [1,20] range.
    :param replacement: Specifies whether the random numbers should
                        be picked with replacement. The default (true)
                        will cause the numbers to be picked with replacement,
                        i.e., the resulting numbers may contain duplicate
                        values (like a series of dice rolls). If you want the
                        numbers picked to be unique (like raffle tickets drawn
                        from a container), set this value to false.
    :return: A list of decimal fraction

    CLI Example:

    .. code-block:: bash

        salt '*' random_org.generateDecimalFractions number=10 decimalPlaces=4

        salt '*' random_org.generateDecimalFractions number=10 decimalPlaces=4 replacement=True

    '''
    ret = {'res': True}

    if not api_key or not api_version:
        try:
            options = __salt__['config.option']('random_org')
            if not api_key:
                api_key = options.get('api_key')
            if not api_version:
                api_version = options.get('api_version')
        except (NameError, KeyError, AttributeError):
            log.error('No Random.org api key found.')
            ret['message'] = 'No Random.org api key or api version found.'
            ret['res'] = False
            return ret

    for item in ['number', 'decimalPlaces']:
        if item not in kwargs:
            ret['res'] = False
            ret['message'] = 'Required argument, {0} is missing.'.format(item)
            return ret

    if not 1 <= kwargs['number'] <= 10000:
        ret['res'] = False
        ret['message'] = 'Number of decimal fractions must be between 1 and 10000'
        return ret

    if not 1 <= kwargs['decimalPlaces'] <= 20:
        ret['res'] = False
        ret['message'] = 'Number of decimal places must be between 1 and 20'
        return ret

    if 'replacement' not in kwargs:
        replacement = True
    else:
        replacement = kwargs['replacement']

    if isinstance(api_version, int):
        api_version = str(api_version)

    log.debug('foo {0}'.format(RANDOM_ORG_FUNCTIONS.get(api_version)))
    _function = RANDOM_ORG_FUNCTIONS.get(api_version).get('generateDecimalFractions').get('method')
    data = {}
    data['id'] = 1911220
    data['jsonrpc'] = '2.0'
    data['method'] = _function
    data['params'] = {'apiKey': api_key,
                      'n': kwargs['number'],
                      'decimalPlaces': kwargs['decimalPlaces'],
                      'replacement': replacement,
                      }

    result = _query(api_version=api_version, data=data)
    if result:
        if 'random' in result:
            random_data = result.get('random').get('data')
            ret['data'] = random_data
        else:
            ret['res'] = False
            ret['message'] = result['message']
    else:
        ret['res'] = False
        ret['message'] = result['message']
    return ret


def generateGaussians(api_key=None,
                      api_version=None,
                      **kwargs):
    '''
    This method generates true random numbers from a
    Gaussian distribution (also known as a normal distribution).

    :param api_key: The Random.org api key.
    :param api_version: The Random.org api version.
    :param number: How many random numbers you need.
                   Must be within the [1,1e4] range.
    :param mean: The distribution's mean. Must be
                 within the [-1e6,1e6] range.
    :param standardDeviation: The distribution's standard
                              deviation. Must be within
                              the [-1e6,1e6] range.
    :param significantDigits: The number of significant digits
                              to use. Must be within the [2,20] range.
    :return: The user list.

    CLI Example:

    .. code-block:: bash

        salt '*' random_org.generateGaussians number=10 mean=0.0 standardDeviation=1.0 significantDigits=8

    '''
    ret = {'res': True}

    if not api_key or not api_version:
        try:
            options = __salt__['config.option']('random_org')
            if not api_key:
                api_key = options.get('api_key')
            if not api_version:
                api_version = options.get('api_version')
        except (NameError, KeyError, AttributeError):
            log.error('No Random.org api key found.')
            ret['message'] = 'No Random.org api key or api version found.'
            ret['res'] = False
            return ret

    for item in ['number', 'mean', 'standardDeviation', 'significantDigits']:
        if item not in kwargs:
            ret['res'] = False
            ret['message'] = 'Required argument, {0} is missing.'.format(item)
            return ret

    if not 1 <= kwargs['number'] <= 10000:
        ret['res'] = False
        ret['message'] = 'Number of decimal fractions must be between 1 and 10000'
        return ret

    if not -1000000 <= kwargs['mean'] <= 1000000:
        ret['res'] = False
        ret['message'] = "The distribution's mean must be between -1000000 and 1000000"
        return ret

    if not -1000000 <= kwargs['standardDeviation'] <= 1000000:
        ret['res'] = False
        ret['message'] = "The distribution's standard deviation must be between -1000000 and 1000000"
        return ret

    if not 2 <= kwargs['significantDigits'] <= 20:
        ret['res'] = False
        ret['message'] = 'The number of significant digits must be between 2 and 20'
        return ret

    if isinstance(api_version, int):
        api_version = str(api_version)

    _function = RANDOM_ORG_FUNCTIONS.get(api_version).get('generateGaussians').get('method')
    data = {}
    data['id'] = 1911220
    data['jsonrpc'] = '2.0'
    data['method'] = _function
    data['params'] = {'apiKey': api_key,
                      'n': kwargs['number'],
                      'mean': kwargs['mean'],
                      'standardDeviation': kwargs['standardDeviation'],
                      'significantDigits': kwargs['significantDigits'],
                      }

    result = _query(api_version=api_version, data=data)
    if result:
        if 'random' in result:
            random_data = result.get('random').get('data')
            ret['data'] = random_data
        else:
            ret['res'] = False
            ret['message'] = result['message']
    else:
        ret['res'] = False
        ret['message'] = result['message']
    return ret


def generateBlobs(api_key=None,
                  api_version=None,
                  **kwargs):
    '''
    List all Slack users.
    :param api_key: The Random.org api key.
    :param api_version: The Random.org api version.
    :param format: Specifies the format in which the
                   blobs will be returned. Values
                   allowed are base64 and hex.
    :return: The user list.

    CLI Example:

    .. code-block:: bash

        salt '*' get_integers number=5 min=1 max=6

        salt '*' get_integers number=5 min=1 max=6
    '''
    ret = {'res': True}

    if not api_key or not api_version:
        try:
            options = __salt__['config.option']('random_org')
            if not api_key:
                api_key = options.get('api_key')
            if not api_version:
                api_version = options.get('api_version')
        except (NameError, KeyError, AttributeError):
            log.error('No Random.org api key found.')
            ret['message'] = 'No Random.org api key or api version found.'
            ret['res'] = False
            return ret

    for item in ['number', 'size']:
        if item not in kwargs:
            ret['res'] = False
            ret['message'] = 'Required argument, {0} is missing.'.format(item)
            return ret

    if not 1 <= kwargs['number'] <= 100:
        ret['res'] = False
        ret['message'] = 'Number of blobs must be between 1 and 100'
        return ret

    # size should be between range and divisible by 8
    if not 1 <= kwargs['size'] <= 1048576 or kwargs['size'] % 8 != 0:
        ret['res'] = False
        ret['message'] = 'Number of blobs must be between 1 and 100'
        return ret

    if 'format' in kwargs:
        _format = kwargs['format']
        if _format not in ['base64', 'hex']:
            ret['res'] = False
            ret['message'] = 'Format must be either base64 or hex.'
            return ret
    else:
        _format = 'base64'

    if isinstance(api_version, int):
        api_version = str(api_version)

    _function = RANDOM_ORG_FUNCTIONS.get(api_version).get('generateBlobs').get('method')
    data = {}
    data['id'] = 1911220
    data['jsonrpc'] = '2.0'
    data['method'] = _function
    data['params'] = {'apiKey': api_key,
                      'n': kwargs['number'],
                      'size': kwargs['size'],
                      'format': _format,
                      }

    result = _query(api_version=api_version, data=data)
    if result:
        if 'random' in result:
            random_data = result.get('random').get('data')
            ret['data'] = random_data
        else:
            ret['res'] = False
            ret['message'] = result['message']
    else:
        ret['res'] = False
        ret['message'] = result['message']
    return ret
