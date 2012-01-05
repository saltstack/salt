'''
Control aspects of the grains data
'''

# Seed the grains dict so cython will build
__grains__ = {}


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
