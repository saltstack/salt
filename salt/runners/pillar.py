# -*- coding: utf-8 -*-
'''
Functions to interact with the pillar compiler on the master
'''

# Import salt libs
import salt.pillar
import salt.utils.minions


def show_top(minion=None, saltenv='base'):
    '''
    Returns the compiled top data for pillar for a specific minion.  If no
    minion is specified, we use the first minion we find.

    CLI Example:

    .. code-block:: bash

        salt-run pillar.show_top
    '''
    id_, grains = salt.utils.minions.get_grains(minion)
    pillar = salt.pillar.Pillar(
        __opts__,
        grains,
        id_,
        saltenv)

    top, errors = pillar.get_top()

    if errors:
        return errors

    return top
