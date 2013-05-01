'''
Extract the pillar data for this minion
'''

# Import third party libs
import yaml

# Import salt libs
import salt.pillar
import salt.utils


def get(key, default=''):
    '''
    .. versionadded:: 0.14

    Attempt to retrieve the named value from pillar, if the named value is not
    available return the passed default. The default return is an empty string.

    The value can also represent a value in a nested dict using a ":" delimiter
    for the dict. This means that if a dict in pillar looks like this:

    {'pkg': {'apache': 'httpd'}}

    To retrieve the value associated with the apache key in the pkg dict this
    key can be passed:

    pkg:apache

    CLI Example::

        salt '*' pillar.get pkg:apache
    '''
    return salt.utils.traverse_dict(__pillar__, key, default)


def data(key=None):
    '''
    Returns the pillar derived from the configured pillar source. The pillar
    source is derived from the file_client option in the minion config

    CLI Example::

        salt '*' pillar.data

    With the optional key argument, you can select a subtree of the
    pillar data.::

        salt '*' pillar.data key='roles'
    '''
    pillar = salt.pillar.get_pillar(
        __opts__,
        __grains__,
        __opts__['id'],
        __opts__['environment'])

    ret = pillar.compile_pillar()

    if key:
        ret = ret.get(key, {})

    return ret
# Allow pillar.items to also be used to return pillar data
items = data


def raw(key=None):
    '''
    Return the raw pillar data that is available in the module. This will
    show the pillar as it is loaded as the __pillar__ dict.

    CLI Example::

        salt '*' pillar.raw

    With the optional key argument, you can select a subtree of the
    pillar raw data.::

        salt '*' pillar.raw key='roles'
    '''
    if key:
        ret = __pillar__.get(key, {})
    else:
        ret = __pillar__

    return ret


def ext(external):
    '''
    Generate the pillar and apply an explicit external pillar

    CLI Example::

        salt '*' pillar.ext 'libvirt: _'
    '''
    if isinstance(external, basestring):
        external = yaml.load(external)
    pillar = salt.pillar.get_pillar(
        __opts__,
        __grains__,
        __opts__['id'],
        __opts__['environment'],
        external)

    ret = pillar.compile_pillar()

    return ret
