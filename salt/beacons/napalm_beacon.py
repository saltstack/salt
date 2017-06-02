# -*- coding: utf-8 -*-
'''
Watch napalm function and fire events.

:depends: - napalm_base Python module >= 0.9.5

:note: The ``napalm`` beacon only works on (proxy) minions.
'''
# Import Python libs
from __future__ import absolute_import
import re

# Import salt libs
from salt.ext import six

# Import third party libs
try:
    import napalm_base
    HAS_NAPALM_BASE = True
except ImportError:
    HAS_NAPALM_BASE = False

__virtualname__ = 'napalm'

import logging
log = logging.getLogger(__name__)


def __virtual__():
    if HAS_NAPALM_BASE:
        return __virtualname__
    return False


def _compare(cur_cmp, cur_struct):
    '''
    Compares two obejcts and return a boolean value
    when there's a match.
    '''
    if isinstance(cur_cmp, dict) and isinstance(cur_struct, dict):
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
        found = False
        for cur_cmp_ele in cur_cmp:
            for cur_struct_ele in cur_struct:
                found |= _compare(cur_cmp_ele, cur_struct_ele)
        return found
    elif isinstance(cur_cmp, bool) and isinstance(cur_struct, bool):
        return cur_cmp == cur_struct
    elif isinstance(cur_cmp, (six.string_types, six.text_type)) and \
         isinstance(cur_struct, (six.string_types, six.text_type)):
        matched = re.match(cur_cmp, cur_struct, re.I)
        if matched:
            return True
        # we can enhance this to allow mathematical operations
        return False
    return False


def beacon(config):
    '''
    Watch napalm function and fire events.

    Example Config

    .. code-block:: yaml

        beacons:
          napalm:
            - net.interfaces:
                '*':
                  is_up: False
            - bgp.neighbors:
                _args:
                  - 172.17.17.1
                global:
                  '*':
                    - up: False
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
            event['tag'] = '{fun}'.format(fun=fun)
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
