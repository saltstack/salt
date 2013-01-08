'''
The sys module provides information about the available functions on the
minion.
'''

def __virtual__():
    '''
    Return as sys
    '''
    return 'sys'


def doc(module=''):
    '''
    Return the docstrings for all modules, these strings are aggregated into
    a single document on the master for easy reading.

    CLI Example::

        salt \* sys.doc
    '''
    docs = {}
    for fun in __salt__:
        if fun.startswith(module):
            docs[fun] = __salt__[fun].__doc__
    return docs


def list_functions(module=''):
    '''
    List the functions.  Optionally, specify a module to list from.

    CLI Example::

        salt \* sys.list_functions
    '''
    names = set()
    for func in __salt__:
        if module:
            if func.startswith('{0}.'.format(module)):
                names.add(func)
        else:
            names.add(func)
    return sorted(names)


def list_modules():
    '''
    List the modules loaded on the minion

    CLI Example::

        salt \* sys.list_modules
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

        salt \* sys.reload_modules
    '''
    # This is handled inside the minion.py file, the function is caught before
    # it ever gets here
    return True
