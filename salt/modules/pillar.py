'''
Extract the pillar data for this minion
'''

# Import salt libs
import salt.pillar
import salt.utils


def get(key, default=''):
    '''
    Attempt to retrive the named value from pillar, if the named value is not
    available return the passed default. The default return is an empty string.

    The value can also represent a value in a nested dict using a ":" delimiter
    for the dict. This means that if a dict in pillar looks like this:

    {'pkg': {'apache': 'httpd'}}

    To retrive the value associated with the apache key in the pkg dict this
    key can be passed:

    pkg:apache

    CLI Example::

        salt '*' pillar.get pkg:apache
    '''
    return salt.utils.traverse_dict(__pillar__, key, default)


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
