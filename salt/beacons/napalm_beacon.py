# -*- coding: utf-8 -*-
'''
NAPALM functions
================

.. versionadded:: 2018.3.0

Watch NAPALM functions and fire events on specific triggers.

.. note::

    The ``NAPALM`` beacon only works only when running under
    a regular Minion or a Proxy Minion, managed via NAPALM_.
    Check the documentation for the
    :mod:`NAPALM proxy module <salt.proxy.napalm>`.

    _NAPALM: http://napalm.readthedocs.io/en/latest/index.html

The configuration accepts a list of Salt functions to be
invoked, and the corresponding output hierarchy that should
be matched against. To invoke a function with certain
arguments, they can be specified using the ``_args`` key, or
``_kwargs`` for more specific key-value arguments.

The match structure follows the output hierarchy of the NAPALM
functions, under the ``out`` key.

For example, the following is normal structure returned by the
:mod:`ntp.stats <salt.modules.napalm_ntp.stats>` execution function:

.. code-block:: json

    {
        "comment": "",
        "result": true,
        "out": [
            {
                "referenceid": ".GPSs.",
                "remote": "172.17.17.1",
                "synchronized": true,
                "reachability": 377,
                "offset": 0.461,
                "when": "860",
                "delay": 143.606,
                "hostpoll": 1024,
                "stratum": 1,
                "jitter": 0.027,
                "type": "-"
            },
            {
                "referenceid": ".INIT.",
                "remote": "172.17.17.2",
                "synchronized": false,
                "reachability": 0,
                "offset": 0.0,
                "when": "-",
                "delay": 0.0,
                "hostpoll": 1024,
                "stratum": 16,
                "jitter": 4000.0,
                "type": "-"
            }
        ]
    }

In order to fire events when the synchronization is lost with
one of the NTP peers, e.g., ``172.17.17.2``, we can match it explicitly as:

.. code-block:: yaml

    ntp.stats:
      remote: 172.17.17.2
      synchronized: false

There is one single nesting level, as the output of ``ntp.stats`` is
just a list of dictionaries, and this beacon will compare each dictionary
from the list with the structure examplified above.

.. note::

    When we want to match on any element at a certain level, we can
    configure ``*`` to match anything.

Considering a more complex structure consisting on multiple nested levels,
e.g., the output of the :mod:`bgp.neighbors <salt.modules.napalm_bgp.neighbors>`
execution function, to check when any neighbor from the ``global``
routing table is down, the match structure would have the format:

.. code-block:: yaml

    bgp.neighbors:
      global:
        '*':
          up: false

The match structure above will match any BGP neighbor, with
any network (``*`` matches any AS number), under the ``global`` VRF.
In other words, this beacon will push an event on the Salt bus
when there's a BGP neighbor down.

The right operand can also accept mathematical operations
(i.e., ``<``, ``<=``, ``!=``, ``>``, ``>=`` etc.) when comparing
numerical values.

Configuration Example:

.. code-block:: yaml

    beacons:
      napalm:
        - net.interfaces:
            # fire events when any interfaces is down
            '*':
              is_up: false
        - net.interfaces:
            # fire events only when the xe-0/0/0 interface is down
            'xe-0/0/0':
              is_up: false
        - ntp.stats:
            # fire when there's any NTP peer unsynchornized
            synchronized: false
        - ntp.stats:
            # fire only when the synchronization
            # with with the 172.17.17.2 NTP server is lost
            _args:
              - 172.17.17.2
            synchronized: false
        - ntp.stats:
            # fire only when there's a NTP peer with
            # synchronization stratum > 5
            stratum: '> 5'

Event structure example:

.. code-block:: json

    salt/beacon/edge01.bjm01/napalm/junos/ntp.stats {
        "_stamp": "2017-09-05T09:51:09.377202",
        "args": [],
        "data": {
            "comment": "",
            "out": [
                {
                    "delay": 0.0,
                    "hostpoll": 1024,
                    "jitter": 4000.0,
                    "offset": 0.0,
                    "reachability": 0,
                    "referenceid": ".INIT.",
                    "remote": "172.17.17.1",
                    "stratum": 16,
                    "synchronized": false,
                    "type": "-",
                    "when": "-"
                }
            ],
            "result": true
        },
        "fun": "ntp.stats",
        "id": "edge01.bjm01",
        "kwargs": {},
        "match": {
            "stratum": "> 5"
        }
    }

The event examplified above has been fired when the device
identified by the Minion id ``edge01.bjm01`` has been synchronized
with a NTP server at a stratum level greater than 5.
'''
from __future__ import absolute_import, unicode_literals

# Import Python std lib
import re
import logging

# Import Salt modules
from salt.ext import six
import salt.utils.napalm

log = logging.getLogger(__name__)
_numeric_regex = re.compile(r'^(<|>|<=|>=|==|!=)\s*(\d+(\.\d+){0,1})$')
# the numeric regex will match the right operand, e.g '>= 20', '< 100', '!= 20', '< 1000.12' etc.
_numeric_operand = {
    '<': '__lt__',
    '>': '__gt__',
    '>=': '__ge__',
    '<=': '__le__',
    '==': '__eq__',
    '!=': '__ne__',
}  # mathematical operand - private method map


__virtualname__ = 'napalm'


def __virtual__():
    '''
    This beacon can only work when running under a regular or a proxy minion, managed through napalm.
    '''
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)


def _compare(cur_cmp, cur_struct):
    '''
    Compares two objects and return a boolean value
    when there's a match.
    '''
    if isinstance(cur_cmp, dict) and isinstance(cur_struct, dict):
        log.debug('Comparing dict to dict')
        for cmp_key, cmp_value in six.iteritems(cur_cmp):
            if cmp_key == '*':
                # matches any key from the source dictionary
                if isinstance(cmp_value, dict):
                    found = False
                    for _, cur_struct_val in six.iteritems(cur_struct):
                        found |= _compare(cmp_value, cur_struct_val)
                    return found
                else:
                    found = False
                    if isinstance(cur_struct, (list, tuple)):
                        for cur_ele in cur_struct:
                            found |= _compare(cmp_value, cur_ele)
                    elif isinstance(cur_struct, dict):
                        for _, cur_ele in six.iteritems(cur_struct):
                            found |= _compare(cmp_value, cur_ele)
                    return found
            else:
                if isinstance(cmp_value, dict):
                    if cmp_key not in cur_struct:
                        return False
                    return _compare(cmp_value, cur_struct[cmp_key])
                if isinstance(cmp_value, list):
                    found = False
                    for _, cur_struct_val in six.iteritems(cur_struct):
                        found |= _compare(cmp_value, cur_struct_val)
                    return found
                else:
                    return _compare(cmp_value, cur_struct[cmp_key])
    elif isinstance(cur_cmp, (list, tuple)) and isinstance(cur_struct, (list, tuple)):
        log.debug('Comparing list to list')
        found = False
        for cur_cmp_ele in cur_cmp:
            for cur_struct_ele in cur_struct:
                found |= _compare(cur_cmp_ele, cur_struct_ele)
        return found
    elif isinstance(cur_cmp, dict) and isinstance(cur_struct, (list, tuple)):
        log.debug('Comparing dict to list (of dicts?)')
        found = False
        for cur_struct_ele in cur_struct:
            found |= _compare(cur_cmp, cur_struct_ele)
        return found
    elif isinstance(cur_cmp, bool) and isinstance(cur_struct, bool):
        log.debug('Comparing booleans: %s ? %s', cur_cmp, cur_struct)
        return cur_cmp == cur_struct
    elif isinstance(cur_cmp, (six.string_types, six.text_type)) and \
         isinstance(cur_struct, (six.string_types, six.text_type)):
        log.debug('Comparing strings (and regex?): %s ? %s', cur_cmp, cur_struct)
        # Trying literal match
        matched = re.match(cur_cmp, cur_struct, re.I)
        if matched:
            return True
        return False
    elif isinstance(cur_cmp, (six.integer_types, float)) and \
         isinstance(cur_struct, (six.integer_types, float)):
        log.debug('Comparing numeric values: %d ? %d', cur_cmp, cur_struct)
        # numeric compare
        return cur_cmp == cur_struct
    elif isinstance(cur_struct, (six.integer_types, float)) and \
         isinstance(cur_cmp, (six.string_types, six.text_type)):
        # Comapring the numerical value agains a presumably mathematical value
        log.debug('Comparing a numeric value (%d) with a string (%s)', cur_struct, cur_cmp)
        numeric_compare = _numeric_regex.match(cur_cmp)
        # determine if the value to compare agains is a mathematical operand
        if numeric_compare:
            compare_value = numeric_compare.group(2)
            return getattr(float(cur_struct), _numeric_operand[numeric_compare.group(1)])(float(compare_value))
        return False
    return False


def validate(config):
    '''
    Validate the beacon configuration.
    '''
    # Must be a list of dicts.
    if not isinstance(config, list):
        return False, 'Configuration for napalm beacon must be a list.'
    for mod in config:
        fun = mod.keys()[0]
        fun_cfg = mod.values()[0]
        if not isinstance(fun_cfg, dict):
            return False, 'The match structure for the {} execution function output must be a dictionary'.format(fun)
        if fun not in __salt__:
            return False, 'Execution function {} is not availabe!'.format(fun)
    return True, 'Valid configuration for the napal beacon!'


def beacon(config):
    '''
    Watch napalm function and fire events.
    '''
    log.debug('Executing napalm beacon with config:')
    log.debug(config)
    ret = []
    for mod in config:
        if not mod:
            continue
        event = {}
        fun = mod.keys()[0]
        fun_cfg = mod.values()[0]
        args = fun_cfg.pop('_args', [])
        kwargs = fun_cfg.pop('_kwargs', {})
        log.debug('Executing {fun} with {args} and {kwargs}'.format(
            fun=fun,
            args=args,
            kwargs=kwargs
        ))
        fun_ret = __salt__[fun](*args, **kwargs)
        log.debug('Got the reply from the minion:')
        log.debug(fun_ret)
        if not fun_ret.get('result', False):
            log.error('Error whilst executing {}'.format(fun))
            log.error(fun_ret)
            continue
        fun_ret_out = fun_ret['out']
        log.debug('Comparing to:')
        log.debug(fun_cfg)
        try:
            fun_cmp_result = _compare(fun_cfg, fun_ret_out)
        except Exception as err:
            log.error(err, exc_info=True)
            # catch any exception and continue
            # to not jeopardise the execution of the next function in the list
            continue
        log.debug('Result of comparison: {res}'.format(res=fun_cmp_result))
        if fun_cmp_result:
            log.info('Matched {fun} with {cfg}'.format(
                fun=fun,
                cfg=fun_cfg
            ))
            event['tag'] = '{os}/{fun}'.format(os=__grains__['os'], fun=fun)
            event['fun'] = fun
            event['args'] = args
            event['kwargs'] = kwargs
            event['data'] = fun_ret
            event['match'] = fun_cfg
            log.debug('Queueing event:')
            log.debug(event)
            ret.append(event)
    log.debug('NAPALM beacon generated the events:')
    log.debug(ret)
    return ret
