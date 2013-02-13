'''
Extract the pillar data for this minion
'''

# Import salt libs
import salt.pillar


def data(key=''):
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

    compiled_pillar = pillar.compile_pillar()

    if key:
        try:
            ret = compiled_pillar[key]
        except KeyError:
            ret = {}
    else:
        ret = compiled_pillar

    return ret


def raw(key=''):
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
        try:
            ret = __pillar__[key]
        except KeyError:
            ret = {}
    else:
        ret = __pillar__

    return ret
