# -*- coding: utf-8 -*-
'''
The sys module provides information about the available functions on the minion
'''

# Import python libs
import logging
import re

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Return as sys
    '''
    return 'sys'


def _strip_rst(docs):
    '''
    Strip/replace reStructuredText directives in docstrings
    '''
    for func, docstring in docs.iteritems():
        if not docstring:
            continue
        docstring_new = re.sub(r' *.. code-block:: \S+\n{1,2}',
                                   '', docstring)
        docstring_new = re.sub('.. note::',
                               'Note:', docstring_new)
        docstring_new = re.sub('.. warning::',
                               'Warning:', docstring_new)
        docstring_new = re.sub('.. versionadded::',
                               'New in version', docstring_new)
        docstring_new = re.sub('.. versionchanged::',
                               'Changed in version', docstring_new)
        if docstring != docstring_new:
            docs[func] = docstring_new


def doc(*args):
    '''
    Return the docstrings for all modules. Optionally, specify a module or a
    function to narrow the selection.

    The strings are aggregated into a single document on the master for easy
    reading.

    Multiple modules/functions can be specified.

    CLI Example:

    .. code-block:: bash

        salt '*' sys.doc
        salt '*' sys.doc sys
        salt '*' sys.doc sys.doc
        salt '*' sys.doc network.traceroute user.info
    '''
    docs = {}
    if not args:
        for fun in __salt__:
            docs[fun] = __salt__[fun].__doc__
        _strip_rst(docs)
        return docs

    for module in args:
        if module:
            # allow both "sys" and "sys." to match sys, without also matching
            # sysctl
            target_mod = module + '.' if not module.endswith('.') else module
        else:
            target_mod = ''
        for fun in __salt__:
            if fun == module or fun.startswith(target_mod):
                docs[fun] = __salt__[fun].__doc__
    _strip_rst(docs)
    return docs


def list_functions(*args, **kwargs):
    '''
    List the functions for all modules. Optionally, specify a module or modules
    from which to list.

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_functions
        salt '*' sys.list_functions sys
        salt '*' sys.list_functions sys user
    '''
    ### NOTE: **kwargs is used here to prevent a traceback when garbage
    ###       arguments are tacked on to the end.

    if not args:
        # We're being asked for all functions
        return sorted(__salt__)

    names = set()
    for module in args:
        if module:
            # allow both "sys" and "sys." to match sys, without also matching
            # sysctl
            module = module + '.' if not module.endswith('.') else module
        for func in __salt__:
            if func.startswith(module):
                names.add(func)
    return sorted(names)


def list_modules():
    '''
    List the modules loaded on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_modules
    '''
    modules = set()
    for func in __salt__:
        comps = func.split('.')
        if len(comps) < 2:
            continue
        modules.add(comps[0])
    return sorted(modules)


def reload_modules():
    '''
    Tell the minion to reload the execution modules

    CLI Example:

    .. code-block:: bash

        salt '*' sys.reload_modules
    '''
    # This is handled inside the minion.py file, the function is caught before
    # it ever gets here
    return True


def argspec(module=''):
    '''
    Return the argument specification of functions in Salt execution
    modules.

    CLI Example:

    .. code-block:: bash

        salt '*' sys.argspec pkg.install
        salt '*' sys.argspec sys
        salt '*' sys.argspec
    '''
    return salt.utils.argspec_report(__salt__, module)
