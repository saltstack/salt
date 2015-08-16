# -*- coding: utf-8 -*-
'''
Support for getting and setting the environment variables
of the current salt process.
'''

# Import python libs
from __future__ import absolute_import
import os

# Import salt libs
import salt.ext.six as six


def __virtual__():
    '''
    No dependency checks, and not renaming, just return True
    '''
    return True


def setenv(name,
           value,
           false_unsets=False,
           clear_all=False,
           update_minion=False):
    '''
    Set the salt process environment variables.

    name
        The environment key to set. Must be a string.

    value
        Either a string or dict. When string, it will be the value
        set for the environment key of 'name' above.
        When a dict, each key/value pair represents an environment
        variable to set.

    false_unsets
        If a key's value is False and false_unsets is True, then the
        key will be removed from the salt processes environment dict
        entirely. If a key's value is False and false_unsets is not
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

    Example:

    .. code-block:: yaml

        a_string_env:
           environ.setenv:
             - name: foo
             - value: bar
             - update_minion: True

        a_dict_env:
           environ.setenv:
             - name: does_not_matter
             - value:
                 foo: bar
                 baz: quux
    '''

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    environ = {}
    if isinstance(value, six.string_types):
        environ[name] = value
    elif isinstance(value, dict):
        environ = value
    else:
        ret['result'] = False
        ret['comment'] = 'Environ value must be string or dict'
        return ret

    if clear_all is True:
        # Any keys not in 'environ' dict supplied by user will be unset
        to_unset = [key for key in os.environ if key not in environ]
        for key in to_unset:
            if false_unsets is not True:
                # This key value will change to ''
                ret['changes'].update({key: ''})
            else:
                # We're going to delete the key
                ret['changes'].update({key: None})

    current_environ = dict(os.environ)
    already_set = []
    for key, val in six.iteritems(environ):
        if val is False:
            # We unset this key from the environment if
            # false_unsets is True. Otherwise we want to set
            # the value to ''
            if current_environ.get(key, None) is None:
                # The key does not exist in environment
                if false_unsets is not True:
                    # This key will be added with value ''
                    ret['changes'].update({key: ''})
            else:
                # The key exists.
                if false_unsets is not True:
                    # Check to see if the value will change
                    if current_environ.get(key, None) != '':
                        # This key value will change to ''
                        ret['changes'].update({key: ''})
                else:
                    # We're going to delete the key
                    ret['changes'].update({key: None})
        elif current_environ.get(key, '') == val:
            already_set.append(key)
        else:
            ret['changes'].update({key: val})

    if __opts__['test']:
        if ret['changes']:
            ret['comment'] = 'Environ values will be changed'
        else:
            ret['comment'] = 'Environ values are already set with the correct values'
        return ret

    if ret['changes']:
        environ_ret = __salt__['environ.setenv'](environ,
                                                 false_unsets,
                                                 clear_all,
                                                 update_minion)
        if not environ_ret:
            ret['result'] = False
            ret['comment'] = 'Failed to set environ variables'
            return ret
        ret['result'] = True
        ret['changes'] = environ_ret
        ret['comment'] = 'Environ values were set'
    else:
        ret['comment'] = 'Environ values were already set with the correct values'
    return ret
