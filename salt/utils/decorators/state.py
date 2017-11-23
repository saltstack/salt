# -*- coding: utf-8 -*-
'''
Decorators for salt.state

:codeauthor: :email:`Bo Maryniuk (bo@suse.de)`
'''

from __future__ import absolute_import
from salt.exceptions import SaltException


def state_output_check(func):
    '''
    Checks for specific types in the state output.
    Raises an Exception in case particular rule is broken.

    :param func:
    :return:
    '''
    def _func(*args, **kwargs):
        '''
        Ruleset.
        '''
        result = func(*args, **kwargs)
        print('is instance of dict:', isinstance(result, dict), 'result:', result)

        if not isinstance(result, dict):
            err_msg = 'Malformed state return, return must be a dict.'
        elif not isinstance(result.get('changes'), dict):
            err_msg = "'Changes' should be a dictionary."
        else:
            missing = []
            for val in ['name', 'result', 'changes', 'comment']:
                if val not in result:
                    missing.append(val)
            if missing:
                err_msg = 'The following keys were not present in the state return: {0}.'.format(', '.join(missing))
            else:
                err_msg = None

        if err_msg:
            raise SaltException(err_msg)
        return result

    return _func


def state_output_unificator(func):
    '''
    While comments as a list are allowed,
    comments needs to be strings for backward compatibility.
    See such claim here: https://github.com/saltstack/salt/pull/43070

    Rules applied:
      - 'comment' is joined into a multi-line string, in case the value is a list.
      - 'result' should be always either True, False or None.

    :param func: module function
    :return: Joins 'comment' list into a multi-line string
    '''
    def _func(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result.get('comment'), list):
            result['comment'] = '\n'.join([str(elm) for elm in result['comment']])
        if result.get('result') is not None:
            result['result'] = bool(result['result'])

        return result

    return _func
