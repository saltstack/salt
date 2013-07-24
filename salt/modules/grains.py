'''
Return/control aspects of the grains data
'''

# Import python libs
import math
import os
import yaml

# Import salt libs
import salt.utils

# Seed the grains dict so cython will build
__grains__ = {}

# Change the default outputter to make it more readable
__outputter__ = {
    'items': 'grains',
    'item': 'grains',
    'setval': 'grains',
}


def _serial_sanitizer(instr):
    '''Replaces the last 1/4 of a string with X's'''
    length = len(instr)
    index = int(math.floor(length * .75))
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


def get(key, default=''):
    '''
    Attempt to retrieve the named value from grains, if the named value is not
    available return the passed default. The default return is an empty string.

    The value can also represent a value in a nested dict using a ":" delimiter
    for the dict. This means that if a dict in grains looks like this:

    {'pkg': {'apache': 'httpd'}}

    To retrieve the value associated with the apache key in the pkg dict this
    key can be passed:

    pkg:apache

    CLI Example::

        salt '*' grains.get pkg:apache
    '''
    return salt.utils.traverse_dict(__grains__, key, default)


def items(sanitize=False):
    '''
    Return all of the minion's grains

    CLI Example::

        salt '*' grains.items

    Sanitized CLI output::

        salt '*' grains.items sanitize=True
    '''
    if salt.utils.is_true(sanitize):
        out = dict(__grains__)
        for key, func in _SANITIZERS.items():
            if key in out:
                out[key] = func(out[key])
        return out
    else:
        return __grains__


def item(*args, **kwargs):
    '''
    Return one or more grains

    CLI Example::

        salt '*' grains.item os
        salt '*' grains.item os osrelease oscodename

    Sanitized CLI Example::

        salt '*' grains.item host sanitize=True
    '''
    ret = {}
    for arg in args:
        try:
            ret[arg] = __grains__[arg]
        except KeyError:
            pass
    if salt.utils.is_true(kwargs.get('sanitize')):
        for arg, func in _SANITIZERS.items():
            if arg in ret:
                ret[arg] = func(ret[arg])
    return ret


def setval(key, val):
    '''
    Set a grains value in the grains config file

    CLI Example::

        salt '*' grains.setval key val
    '''
    grains = {}
    if os.path.isfile(__opts__['conf_file']):
        gfn = os.path.join(
            os.path.dirname(__opts__['conf_file']),
            'grains'
        )
    elif os.path.isdir(__opts__['conf_file']):
        gfn = os.path.join(
            __opts__['conf_file'],
            'grains'
        )
    else:
        gfn = os.path.join(
            os.path.dirname(__opts__['conf_file']),
            'grains'
        )

    if os.path.isfile(gfn):
        with salt.utils.fopen(gfn, 'rb') as fp_:
            try:
                grains = yaml.safe_load(fp_.read())
            except Exception as e:
                return 'Unable to read existing grains file: {0}'.format(e)
        if not isinstance(grains, dict):
            grains = {}
    grains[key] = val
    cstr = yaml.safe_dump(grains, default_flow_style=False)
    with salt.utils.fopen(gfn, 'w+') as fp_:
        fp_.write(cstr)
    fn_ = os.path.join(__opts__['cachedir'], 'module_refresh')
    with salt.utils.fopen(fn_, 'w+') as fp_:
        fp_.write('')
    # Sync the grains
    __salt__['saltutil.sync_grains']()
    # Return the grain we just set to confirm everything was OK
    return {key: val}


def append(key, val):
    '''
    Append a value to a list in the grains config file

    CLI Example::

        salt '*' grains.append key val
    '''
    grains = get(key, [])
    if not isinstance(grains, list):
        return 'The key {0} is not a valid list'.format(key)
    if val in grains:
        return 'The val {0} was already in the list {1}'.format(val, key)
    grains.append(val)
    return setval(key, grains)


def remove(key, val):
    '''
    Remove a value from a list in the grains config file

    CLI Example::

        salt '*' grains.remove key val
    '''
    grains = get(key, [])
    if not isinstance(grains, list):
        return 'The key {0} is not a valid list'.format(key)
    if val not in grains:
        return 'The val {0} was not in the list {1}'.format(val, key)
    grains.remove(val)
    return setval(key, grains)


def delval(key):
    '''
    Delete a grain from the grains config file

    CLI Example::

        salt '*' grains.delval key
    '''
    setval(key, None)


def ls():  # pylint: disable=C0103
    '''
    Return a list of all available grains

    CLI Example::

        salt '*' grains.ls
    '''
    return sorted(__grains__)
