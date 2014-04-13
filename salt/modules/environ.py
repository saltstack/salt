# -*- coding: utf-8 -*-
'''
Support for getting and setting the environment variables
of the current salt process.
'''

# Import python libs
import os
import logging

# Import salt libs
from salt._compat import string_types

log = logging.getLogger(__name__)


def __virtual__():
    '''
    No dependency checks, and not renaming, just return True
    '''
    return True


def setval(key, val, false_unsets=False):
    '''
    Set a single salt process environment variable. Returns True
    on success.

    key
        The environment key to set. Must be a string.

    val
        The value to set. Must be a string or False. Refer to the
        'false_unsets' parameter for behavior when set to False.

    false_unsets
        If val is False and false_unsets is True, then the key will be
        removed from the salt processes environment dict entirely.
        If val is False and false_unsets is not True, then the key's
        value will be set to an empty string.
        Default: False.


    CLI Example:

    .. code-block:: bash

        salt '*' environ.setval foo bar
        salt '*' environ.setval baz val=False false_unsets=True
    '''
    if not isinstance(key, string_types):
        log.debug(
            '{0}: "key" argument is not a string type: {1!r}'
            .format(__name__, key)
        )
    if val is False:
        if false_unsets is True:
            try:
                os.environ.pop(key, None)
                return None
            except Exception as exc:
                log.error(
                    '{0}: Exception occurred when unsetting '
                    'environ key "{1!r}": {2!r}'
                    .format(__name__, key, exc)
                )
                return False
        else:
            val = ''
    if isinstance(val, string_types):
        try:
            os.environ[key] = val
            return os.environ[key]
        except Exception as exc:
            log.error(
                '{0}: Exception occurred when setting'
                'environ key "{1!r}": {2!r}'
                .format(__name__, key, exc)
            )
            return False
    else:
        log.debug(
            '{0}: "val" argument for key "{1!r}" is not a string '
            'or False: {2!r}'
            .format(__name__, key, val)
        )
        return False


def setenv(environ, false_unsets=False, clear_all=False, update_minion=False):
    '''
    Set multiple salt process environment variables from a dict.
    Returns a dict.

    environ
        Must be a dict. The top-level keys of the dict are the names
        of the environment variables to set. Each key's value must be
        a string or False. Refer to the 'false_unsets' parameter for
        behavior when a value set to False.

    false_unsets
        If a key's value is False and false_unsets is True, then the
        key will be removed from the salt processes environment dict
        entirely. If a key's value is Flase and false_unsets is not
        True, then the key's value will be set to an empty string.
        Default: False

    clear_all
        USE WITH CAUTION! This option can unset environment variables
        needed for salt to function properly.
        If clear_all is True, then any environment variables not
        defined in the environ dict will be deleted.
        Default: False

    update_minion
        If True, apply these environ changes to the main salt-minion
        process. If False, the environ changes will only affect the
        current salt subprocess.
        Default: False


    CLI Example:

    .. code-block:: bash

        salt '*' environ.setenv '{"foo": "bar", "baz": "quux"}'
        salt '*' environ.setenv '{"a": "b", "c": False}' false_unsets=True
    '''
    ret = {}
    if not isinstance(environ, dict):
        log.debug(
            '{0}: "environ" argument is not a dict: {1!r}'
            .format(__name__, environ)
        )
        return False
    if clear_all is True:
        # Unset any keys not defined in 'environ' dict supplied by user
        to_unset = [key for key in os.environ.keys() if key not in environ]
        for key in to_unset:
            ret[key] = setval(key, False, false_unsets)
    for key, val in environ.items():
        if isinstance(val, string_types):
            ret[key] = setval(key, val)
        elif val is False:
            ret[key] = setval(key, val, false_unsets)
        else:
            log.debug(
                '{0}: "val" argument for key "{1!r}" is not a string '
                'or False: {2!r}'
                .format(__name__, key, val)
            )
            return False

    if update_minion is True:
        __salt__['event.fire']({'environ': environ,
                                'false_unsets': false_unsets,
                                'clear_all': clear_all
                                },
                               'environ_setenv')
    return ret


def get(key, default=''):
    '''
    Get a single salt process environment variable.

    key
        String used as the key for environment lookup.

    default
        If the key is not found in the enironment, return this value.
        Default: ''


    CLI Example:

    .. code-block:: bash

        salt '*' environ.get foo
        salt '*' environ.get baz default=False
    '''
    if not isinstance(key, string_types):
        log.debug(
            '{0}: "key" argument is not a string type: {1!r}'
            .format(__name__, key)
        )
        return False
    return os.environ.get(key, default)


def has_value(key, value=None):
    '''
    Determine whether the key exists in the current salt process
    environment dictionary. Optionally compare the current value
    of the environment against the supplied value string.

    key
        Must be a string. Used as key for environment lookup.

    value:
        Optional. If key exists in the environment, compare the
        current value with this value. Return True if they are equal.

    CLI Example:

    .. code-block:: bash

        salt '*' environ.has_value foo
    '''
    if not isinstance(key, string_types):
        log.debug(
            '{0}: "key" argument is not a string type: {1!r}'
            .format(__name__, key)
        )
        return False
    try:
        cur_val = os.environ[key]
        if value is not None:
            if cur_val == value:
                return True
            else:
                return False
    except KeyError:
        return False
    return True


def item(keys, default=''):
    '''
    Get one or more salt process environment variables.
    Returns a dict.

    keys
        Either a string or a list of strings that will be used as the
        keys for environment lookup.

    default
        If the key is not found in the enironment, return this value.
        Default: ''

    CLI Example:

    .. code-block:: bash

        salt '*' environ.item foo
        salt '*' environ.item '[foo, baz]' default=None
    '''
    ret = {}
    key_list = []
    if isinstance(keys, string_types):
        key_list.append(keys)
    elif isinstance(keys, list):
        key_list = keys
    else:
        log.debug(
            '{0}: "keys" argument is not a string or list type: {1!r}'
            .format(__name__, keys)
        )
    for key in key_list:
        ret[key] = os.environ.get(key, default)
    return ret


def items():
    '''
    Return a dict of the entire environment set for the salt process

    CLI Example:

    .. code-block:: bash

        salt '*' environ.items
    '''
    return dict(os.environ)
