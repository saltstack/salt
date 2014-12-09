# -*- coding: utf-8 -*-
'''
The sys module provides information about the available functions on the minion
'''

# Import python libs
import logging

# Import salt libs
import salt.loader
import salt.utils
import salt.state
from salt.utils.doc import strip_rst as _strip_rst

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'sys'

__proxyenabled__ = '*'


def __virtual__():
    '''
    Return as sys
    '''
    return __virtualname__


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
        return _strip_rst(docs)

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
    return _strip_rst(docs)


def state_doc(*args):
    '''
    .. versionadded:: 2014.7.0

    Return the docstrings for all states. Optionally, specify a state or a
    function to narrow the selection.

    The strings are aggregated into a single document on the master for easy
    reading.

    Multiple states/functions can be specified.

    CLI Example:

    .. code-block:: bash

        salt '*' sys.state_doc
        salt '*' sys.state_doc service
        salt '*' sys.state_doc service.running
        salt '*' sys.state_doc service.running ipables.append
    '''
    st_ = salt.state.State(__opts__)

    docs = {}
    if not args:
        for fun in st_.states:
            state = fun.split('.')[0]
            if state not in docs:
                if hasattr(st_.states[fun], '__globals__'):
                    docs[state] = st_.states[fun].__globals__['__doc__']
            docs[fun] = st_.states[fun].__doc__
        return _strip_rst(docs)

    for module in args:
        if module:
            # allow both "sys" and "sys." to match sys, without also matching
            # sysctl
            target_mod = module + '.' if not module.endswith('.') else module
        else:
            target_mod = ''
        for fun in st_.states:
            if fun == module or fun.startswith(target_mod):
                state = module.split('.')[0]
                if state not in docs:
                    if hasattr(st_.states[fun], '__globals__'):
                        docs[state] = st_.states[fun].__globals__['__doc__']
                docs[fun] = st_.states[fun].__doc__
    return _strip_rst(docs)


def runner_doc(*args):
    '''
    .. versionadded:: 2014.7.0

    Return the docstrings for all runners. Optionally, specify a runner or a
    function to narrow the selection.

    The strings are aggregated into a single document on the master for easy
    reading.

    Multiple runners/functions can be specified.

    CLI Example:

    .. code-block:: bash

        salt '*' sys.runner_doc
        salt '*' sys.runner_doc cache
        salt '*' sys.runner_doc cache.grains
        salt '*' sys.runner_doc cache.grains mine.get
    '''
    run_ = salt.runner.Runner(__opts__)
    docs = {}
    if not args:
        for fun in run_.functions:
            docs[fun] = run_.functions[fun].__doc__
        return _strip_rst(docs)

    for module in args:
        if module:
            # allow both "sys" and "sys." to match sys, without also matching
            # sysctl
            target_mod = module + '.' if not module.endswith('.') else module
        else:
            target_mod = ''
        for fun in run_.functions:
            if fun == module or fun.startswith(target_mod):
                docs[fun] = run_.functions[fun].__doc__
    return _strip_rst(docs)


def returner_doc(*args):
    '''
    .. versionadded:: 2014.7.0

    Return the docstrings for all returners. Optionally, specify a returner or a
    function to narrow the selection.

    The strings are aggregated into a single document on the master for easy
    reading.

    Multiple returners/functions can be specified.

    CLI Example:

    .. code-block:: bash

        salt '*' sys.returner_doc
        salt '*' sys.returner_doc sqlite3
        salt '*' sys.returner_doc sqlite3.get_fun
        salt '*' sys.returner_doc sqlite3.get_fun etcd.get_fun
    '''
    returners_ = salt.loader.returners(__opts__, [])
    docs = {}
    if not args:
        for fun in returners_:
            docs[fun] = returners_[fun].__doc__
        return _strip_rst(docs)

    for module in args:
        if module:
            # allow both "sys" and "sys." to match sys, without also matching
            # sysctl
            target_mod = module + '.' if not module.endswith('.') else module
        else:
            target_mod = ''
        for fun in returners_:
            if fun == module or fun.startswith(target_mod):
                docs[fun] = returners_[fun].__doc__
    return _strip_rst(docs)


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


def list_state_functions(*args, **kwargs):
    '''
    .. versionadded:: 2014.7.0

    List the functions for all state modules. Optionally, specify a state
    module or modules from which to list.

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_state_functions
        salt '*' sys.list_state_functions file
        salt '*' sys.list_state_functions pkg user
    '''
    ### NOTE: **kwargs is used here to prevent a traceback when garbage
    ###       arguments are tacked on to the end.

    st_ = salt.state.State(__opts__)
    if not args:
        # We're being asked for all functions
        return sorted(st_.states)

    names = set()
    for module in args:
        if module:
            # allow both "sys" and "sys." to match sys, without also matching
            # sysctl
            module = module + '.' if not module.endswith('.') else module
        for func in st_.states:
            if func.startswith(module):
                names.add(func)
    return sorted(names)


def list_state_modules():
    '''
    .. versionadded:: 2014.7.0

    List the modules loaded on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_state_modules
    '''
    st_ = salt.state.State(__opts__)
    modules = set()
    for func in st_.states:
        comps = func.split('.')
        if len(comps) < 2:
            continue
        modules.add(comps[0])
    return sorted(modules)


def list_runners():
    '''
    .. versionadded:: 2014.7.0

    List the runners loaded on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_runners
    '''
    run_ = salt.runner.Runner(__opts__)
    runners = set()
    for func in run_.functions:
        comps = func.split('.')
        if len(comps) < 2:
            continue
        runners.add(comps[0])
    return sorted(runners)


def list_runner_functions(*args, **kwargs):
    '''
    .. versionadded:: 2014.7.0

    List the functions for all runner modules. Optionally, specify a runner
    module or modules from which to list.

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_runner_functions
        salt '*' sys.list_runner_functions state
        salt '*' sys.list_runner_functions state virt
    '''
    ### NOTE: **kwargs is used here to prevent a traceback when garbage
    ###       arguments are tacked on to the end.

    run_ = salt.runner.Runner(__opts__)
    if not args:
        # We're being asked for all functions
        return sorted(run_.functions)

    names = set()
    for module in args:
        if module:
            # allow both "sys" and "sys." to match sys, without also matching
            # sysctl
            module = module + '.' if not module.endswith('.') else module
        for func in run_.functions:
            if func.startswith(module):
                names.add(func)
    return sorted(names)


def list_returners():
    '''
    .. versionadded:: 2014.7.0

    List the runners loaded on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_returners
    '''
    returners_ = salt.loader.returners(__opts__, [])
    returners = set()
    for func in returners_:
        comps = func.split('.')
        if len(comps) < 2:
            continue
        returners.add(comps[0])
    return sorted(returners)


def list_returner_functions(*args, **kwargs):
    '''
    .. versionadded:: 2014.7.0

    List the functions for all returner modules. Optionally, specify a returner
    module or modules from which to list.

    CLI Example:

    .. code-block:: bash

        salt '*' sys.list_returner_functions
        salt '*' sys.list_returner_functions mysql
        salt '*' sys.list_returner_functions mysql etcd
    '''
    ### NOTE: **kwargs is used here to prevent a traceback when garbage
    ###       arguments are tacked on to the end.

    returners_ = salt.loader.returners(__opts__, [])
    if not args:
        # We're being asked for all functions
        return sorted(returners_)

    names = set()
    for module in args:
        if module:
            # allow both "sys" and "sys." to match sys, without also matching
            # sysctl
            module = module + '.' if not module.endswith('.') else module
        for func in returners_:
            if func.startswith(module):
                names.add(func)
    return sorted(names)
