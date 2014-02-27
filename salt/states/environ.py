# -*- coding: utf-8 -*-
'''
Support for getting and setting the environment variables
of the current salt process.
'''

# Import python libs
import os

# Import salt libs
from salt._compat import string_types

__func_alias__ = {
    'set_': 'set'
}


def __virtual__():
    '''
    No dependency checks, and not renaming, just return True
    '''
    return True


def set_(name, value):
    '''
    Set the salt process environment variables.

    name
        The environment variable key to set if 'value' is a string

    value
        Either a string or dict. When string, it will be the value
        set for the environment variable of 'name' above.
        When a dict, each key/value pair represents an environment
        variable to set.

    CLI Example:

    .. code-block:: yaml

        a_string_env:
           environ.set:
             - name: foo
             - value: bar

        a_dict_env:
           environ.set:
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
    if isinstance(value, string_types):
        environ[name] = value
    elif isinstance(value, dict):
        environ = value
    else:
        ret['result'] = False
        ret['comment'] = 'Environ value must be string or dict'
        return ret
    current_environ = dict(os.environ)
    already_set = []
    for key, val in environ.items():
        if current_environ.get(key, '') == val:
            already_set.append(key)
            environ.pop(key)
        else:
            ret['changes'].update({key: val})

    if __opts__['test']:
        ret['result'] = None
        if ret['changes']:
            ret['comment'] = 'Environ values will be changed'.format(name)
        else:
            ret['comment'] = 'Environ values are already set with the correct values'
        return ret

    environ_ret = __salt__['environ.set'](environ)
    if not environ_ret:
        ret['result'] = False
        ret['comment'] = 'Failed to set environ variables'
        return ret
    ret['result'] = True
    ret['changes'] = environ_ret
    ret['comment'] = 'Environ values were set'
    return ret
