'''
Extract the pillar data for this minion
'''

# Import Salt libs
import salt.pillar


def data():
    '''
    Returns the pillar derived from the configured pillar source. The pillar
    source is derived from the file_client option in the minion config

    CLI Example::

        salt '*' pillar.data
    '''
    pillar = salt.pillar.get_pillar(
            __opts__,
            __grains__,
            __opts__['id'],
            __opts__['environment'])
    return pillar.compile_pillar()


def raw():
    '''
    Return the raw pillar data that is available in the module. This will
    show the pillar as it is loaded as the __pillar__ dict.

    CLI Example::

        salt '*' pillar.raw
    '''
    return __pillar__
