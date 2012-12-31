'''
Control aspects of the grains data
'''

# Import python libs
from math import floor

# Seed the grains dict so cython will build
__grains__ = {}

# Change the default outputter to make it more readable
__outputter__ = {
    'item': 'txt',
    'ls': 'grains',
    'items': 'grains',
}


def _serial_sanitizer(instr):
    '''Replaces the last 1/4 of a string with X's'''
    length = len(instr)
    index = int(floor(length * .75))
    return "{0}{1}".format(instr[:index], 'X' * (length - index))


_FQDN_SANITIZER = lambda x: 'MINION.DOMAINNAME'
_HOSTNAME_SANITIZER = lambda x: 'MINION'
_DOMAINNAME_SANITIZER = lambda x: 'DOMAINNAME'


# A dictionary of grain -> function mappings for sanitizing grain output. This
# is used when the 'sanitize' flag is given.
_SANITIZERS = {
    'serialnumber': _serial_sanitizer,
    'domain': _DOMAINNAME_SANITIZER,
    'fqdn': _FQDN_SANITIZER,
    'id': _FQDN_SANITIZER,
    'host': _HOSTNAME_SANITIZER,
    'localhost': _HOSTNAME_SANITIZER,
    'nodename': _HOSTNAME_SANITIZER,
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
        for key, func in _SANITIZERS.items():
            if key in out:
                out[key] = func(out[key])
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
    if sanitize and key in _SANITIZERS:
        return _SANITIZERS[key](__grains__.get(key, ''))
    else:
        return __grains__.get(key, '')


def ls():  # pylint: disable-msg=C0103
    '''
    Return a list of all available grains

    CLI Example::

        salt '*' grains.ls
    '''
    return sorted(__grains__)
