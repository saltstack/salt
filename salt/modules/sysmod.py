'''
The sys module provides information about the available functions on the
minion.
'''

# Import python libs
import logging

# Import salt libs
# TODO: should probably use _getargs() from salt.utils?
from salt.state import _getargs

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Return as sys
    '''
    return 'sys'


def doc(module=''):
    '''
    Return the docstrings for all modules. Optionally, specify a module or a
    function to narrow the selection.

    The strings are aggregated into a single document on the master for easy
    reading.

    CLI Example::

        salt '*' sys.doc
        salt '*' sys.doc sys
        salt '*' sys.doc sys.doc
    '''
    docs = {}
    if module:
        # allow both "sys" and "sys." to match sys, without also matching
        # sysctl
        target_mod = module + '.' if not module.endswith('.') else module
    else:
        target_mod = ''
    for fun in __salt__:
        if fun == module or fun.startswith(target_mod):
            docs[fun] = __salt__[fun].__doc__
    return docs


def list_functions(module=''):
    '''
    List the functions for all modules. Optionally, specify a module to list
    from.

    CLI Example::

        salt '*' sys.list_functions
        salt '*' sys.list_functions sys
    '''
    names = set()
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

    CLI Example::

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

    CLI Example::

        salt '*' sys.reload_modules
    '''
    # This is handled inside the minion.py file, the function is caught before
    # it ever gets here
    return True

def argspec(module=''):
    '''
    Return the argument specification of functions in Salt execution
    modules.

    CLI Example::

        salt '*' sys.argspec pkg.install
        salt '*' sys.argspec sys
        salt '*' sys.argspec
    '''
    ret = {}
    # TODO: cp.get_file will also match cp.get_file_str. this is the
    # same logic as sys.doc, and it is not working as expected, see
    # issue #3614
    if module:
        # allow both "sys" and "sys." to match sys, without also matching
        # sysctl
        comps = module.split('.')
        comps = filter(None, comps)
        if len(comps) < 2:
            module = module + '.' if not module.endswith('.') else module
    for fun in __salt__:
        if fun.startswith(module):
            try:
                aspec = _getargs(__salt__[fun])
            except TypeError:
                # this happens if not callable
                continue

            args, varargs, kwargs, defaults = aspec

            ret[fun] = {}
            ret[fun]['args'] = args if args else None
            ret[fun]['defaults'] = defaults if defaults else None
            ret[fun]['varargs'] = True if varargs else None
            ret[fun]['kwargs'] = True if kwargs else None

    return ret
