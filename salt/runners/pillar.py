# -*- coding: utf-8 -*-
'''
Functions to interact with the pillar compiler on the master
'''

# Import salt libs
import salt.pillar


def show_top():
    '''
    Returns the compiled top data for pillar

    CLI Example:

    .. code-block:: bash

        salt-run pillar.show_top
    '''
    pillar = salt.pillar.Pillar(
        __opts__,
        {},
        __opts__['id'],
        __opts__['environment'])

    top, errors = pillar.get_top()

    if errors:
        return errors

    return top
