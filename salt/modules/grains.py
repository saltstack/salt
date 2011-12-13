'''
Control aspects of the grains data
'''

# Seed the grains dict so cython will build
__grains__ = {}

# Change the default outputter to make it more readable
__outputter__ = {
    'item' : 'txt',
    'items': 'yaml',
}


def items():
    '''
    Return the grains data

    CLI Example::

        salt '*' grains.items
    '''
    return __grains__


def item(key):
    '''
    Return a singe component of the grains data

    CLI Example::

        salt '*' grains.item os
    '''
    if key in __grains__:
        return __grains__[key]
    return ''

def list():
    '''
    Return a list of all available grains

    CLI Example::

        salt '*' grains.list
    '''
    return sorted(__grains__.keys())

# Keep the wise 'nix beards happy
ls = list
