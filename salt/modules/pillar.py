'''
Extract the pillar data for this minion
'''

# Import third party libs
import yaml

# Import salt libs
import salt.pillar


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
