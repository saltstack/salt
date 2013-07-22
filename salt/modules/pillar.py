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


def items(*args):
    '''
    This function calls the master for a fresh pillar and generates the pillar
    data on the fly, unlike pillar.raw which returns the pillar data which
    is currently loaded into the minion.

    CLI Example::

        salt '*' pillar.items
    '''
    # Preserve backwards compatibility
    if args:
        return item(*args)

    pillar = salt.pillar.get_pillar(
        __opts__,
        __grains__,
        __opts__['id'],
        __opts__['environment'])

    return pillar.compile_pillar()

# Allow pillar.data to also be used to return pillar data
data = items


def item(*args):
    '''
    .. versionadded:: 0.16.1

    Return one ore more pillar entries

    CLI Examples::

        salt '*' pillar.item foo
        salt '*' pillar.item foo bar baz
    '''
    ret = {}
    pillar = items()
    for arg in args:
        try:
            ret[arg] = pillar[arg]
        except KeyError:
            pass
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
