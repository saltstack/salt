'''
Control aspects of the grains data
'''

# Import python libs
import math
import os
import yaml

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


def item(*args, **kargs):
    '''
    Return a single component of the grains data

    CLI Example::

        salt '*' grains.item os
        
    Return multiple components of the grains data

    CLI Example::

        salt '*' grains.item os osrelease oscodename
        
    Sanitized CLI Example::

        salt '*' grains.item host sanitize=True
    '''
    ret = {}
    for k in args:
        if k in __grains__:
            ret[k] = __grains__[k]
    if 'sanitize' in kargs:
        for k, func in _SANITIZERS.items():
            if k in ret:
                ret[k] = func(ret[k])
        return ret
    else:
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
    if os.path.isfile(gfn):
        with open(gfn, 'rb') as fp_:
            try:
                grains = yaml.safe_load(fp_.read())
            except Exception, e:
                return 'Unable to read existing grains file: %s' %e
    grains[key] = val
    cstr = yaml.safe_dump(grains, default_flow_style=False)
    with open(gfn, 'w+') as fp_:
        fp_.write(cstr)
    fn_ = os.path.join(__opts__['cachedir'], 'module_refresh')
    with open(fn_, 'w+') as fp_:
        fp_.write('')
    # Return the grain we just set to confirm everything was OK
    return {key: val}


def ls():  # pylint: disable-msg=C0103
    '''
    Return a list of all available grains

    CLI Example::

        salt '*' grains.ls
    '''
    return sorted(__grains__)
