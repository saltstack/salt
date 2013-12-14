# -*- coding: utf-8 -*-
'''
Functions to interact with the pillar compiler on the master
'''

# Import salt libs
import salt.pillar
import salt.utils.minions
import salt.output


def show_top(minion=None, saltenv='base'):
    '''
    Returns the compiled top data for pillar for a specific minion.  If no
    minion is specified, we use the first minion we find.

    CLI Example:

    .. code-block:: bash

        salt-run pillar.show_top
    '''
    id_, grains, _ = salt.utils.minions.get_minion_data(minion, __opts__)
    pillar = salt.pillar.Pillar(
        __opts__,
        grains,
        id_,
        saltenv)

    top, errors = pillar.get_top()

    if errors:
        salt.output.display_output(errors, 'nested', __opts__)
        return errors

    salt.output.display_output(top, 'nested', __opts__)
    return top
