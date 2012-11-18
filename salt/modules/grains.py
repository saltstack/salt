'''
Control aspects of the grains data
'''

from math import floor

# Seed the grains dict so cython will build
__grains__ = {}

# Change the default outputter to make it more readable
__outputter__ = {
    'item': 'txt',
    'items': 'yaml',
}


def _serial_sanitizer(instr):
    '''Replaces the last 1/4 of a string with X's'''
    length = len(instr)
    index = int(floor(length * .75))
    return "{0}{1}".format(instr[:index], 'X' * (length - index))

_fqdn_sanitizer = lambda x: 'MINION.DOMAINNAME'
_hostname_sanitizer = lambda x: 'MINION'
_domainname_sanitizer = lambda x: 'DOMAINNAME'

# A dictionary of grain -> function mappings for sanitizing grain output. This
# is used when the 'sanitize' flag is given.
_sanitizers = {
    'serialnumber': _serial_sanitizer,
    'domain': _domainname_sanitizer,
    'fqdn': _fqdn_sanitizer,
    'id': _fqdn_sanitizer,
    'host': _hostname_sanitizer,
    'localhost': _hostname_sanitizer,
    'nodename': _hostname_sanitizer,
}


def items(sanitize=False):
    '''
    Return the grains data

    CLI Example::

        salt '*' grains.items

    Sanitized CLI output::

        salt '*' grains.items sanitize=True
    '''
    if sanitize:
        out = dict(__grains__)
        for (k, f) in _sanitizers.items():
            if k in out:
                out[k] = f(out[k])
        return out
    else:
        return __grains__


def item(key=None, sanitize=False):
    '''
    Return a singe component of the grains data

    CLI Example::

        salt '*' grains.item os

    Sanitized CLI output::

        salt '*' grains.items serialnumber sanitize=True
    '''
    if sanitize and key in _sanitizers:
        return _sanitizers[key](_grains__.get(key, ''))
    else:
        return __grains__.get(key, '')


def ls():
    '''
    Return a list of all available grains

    CLI Example::

        salt '*' grains.ls
    '''
    return sorted(__grains__)
