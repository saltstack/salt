# -*- coding: utf-8 -*-
'''
NAPALM functions
================

Watch napalm functions and fire events on specific triggers.

.. versionadded:: Oxygen

.. note::
    The ``napalm`` beacon only work only when running under
    a regular or a proxy minion.

The configuration accepts a list of Salt functions to be
invoked, and the corresponding output hierarchy that should
be matched against. When we want to match on any element
at a certain level, we can have ``*`` to match anything.

To invoke a certain function with certain arguments,
they can be specified using the ``_args`` key, or
``_kwargs`` to configure more specific key-value arguments.

The right operand can also accept mathematical comparisons
when applicable (i.e., ``<``, ``<=``, ``!=``, ``>``, ``>=`` etc.).

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
        - bgp.neighbors:
            # fire events only when the 172.17.17.1 BGP neighbor is down
            _args:
              - 172.17.17.1
            global:
              '*':
                up: false
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
'''
from __future__ import absolute_import

# Import Python std lib
import re
import logging

# Import Salt modules
from salt.ext import six
import salt.utils.napalm

log = logging.getLogger(__name__)
_numeric_regex = re.compile('^(<|>|<=|>=|==|!=)\s*(\d+(\.\d+){0,1})$')
_numeric_operand = {
    '<': '__lt__',
    '>': '__gt__',
    '>=': '__ge__',
    '<=': '__le__',
    '==': '__eq__',
    '!=': '__ne__',
}

__virtualname__ = 'napalm'


def __virtual__():
    '''
    This beacon can only work when running under a regular or a proxy minion.
    '''
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)


def _compare(cur_cmp, cur_struct):
    '''
    Compares two obejcts and return a boolean value
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
        log.debug('Comparing booleans')
        return cur_cmp == cur_struct
    elif isinstance(cur_cmp, (six.string_types, six.text_type)) and \
         isinstance(cur_struct, (six.string_types, six.text_type)):
        log.debug('Comparing strings (and regex?)')
        # Trying literal match
        matched = re.match(cur_cmp, cur_struct, re.I)
        if matched:
            return True
        return False
    elif isinstance(cur_cmp, (six.integer_types, float)) and \
         isinstance(cur_struct, (six.integer_types, float)):
        log.debug('Comparing numeric values')
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
            log.error('Error whilst executing {fun}'.format(fun))
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
