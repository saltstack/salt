'''
Extract the pillar data for this minion
'''

# Import Salt modules
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
