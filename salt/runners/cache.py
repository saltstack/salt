# -*- coding: utf-8 -*-
'''
Return cached data from minions
'''
# Import python libs
import logging

# Import salt libs
import salt.log
import salt.utils.master
import salt.output
import salt.payload
from salt._compat import string_types

log = logging.getLogger(__name__)

deprecation_warning = ("The 'minion' arg will be removed from "
                    "cache.py runner. Specify minion with 'tgt' arg!")


def grains(tgt=None, expr_form='glob', **kwargs):
    '''
    Return cached grains of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.grains
    '''
    deprecated_minion = kwargs.get('minion', None)
    if tgt is None and deprecated_minion is None:
        log.warn("DEPRECATION WARNING: {0}".format(deprecation_warning))
        tgt = '*'  # targat all minions for backward compatibility
    elif tgt is None and isinstance(deprecated_minion, string_types):
        log.warn("DEPRECATION WARNING: {0}".format(deprecation_warning))
        tgt = deprecated_minion
    elif tgt is None:
        return {}
    pillar_util = salt.utils.master.MasterPillarUtil(tgt, expr_form,
                                                use_cached_grains=True,
                                                grains_fallback=False,
                                                opts=__opts__)
    cached_grains = pillar_util.get_minion_grains()
    salt.output.display_output(cached_grains, None, __opts__)
    return cached_grains


def pillar(tgt=None, expr_form='glob', **kwargs):
    '''
    Return cached pillars of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.pillar
    '''
    deprecated_minion = kwargs.get('minion', None)
    if tgt is None and deprecated_minion is None:
        log.warn("DEPRECATION WARNING: {0}".format(deprecation_warning))
        tgt = '*'  # targat all minions for backward compatibility
    elif tgt is None and isinstance(deprecated_minion, string_types):
        log.warn("DEPRECATION WARNING: {0}".format(deprecation_warning))
        tgt = deprecated_minion
    elif tgt is None:
        return {}
    pillar_util = salt.utils.master.MasterPillarUtil(tgt, expr_form,
                                                use_cached_grains=True,
                                                grains_fallback=False,
                                                use_cached_pillar=True,
                                                pillar_fallback=False,
                                                opts=__opts__)
    cached_pillar = pillar_util.get_minion_pillar()
    salt.output.display_output(cached_pillar, None, __opts__)
    return cached_pillar


def mine(tgt=None, expr_form='glob', **kwargs):
    '''
    Return cached mine data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.mine
    '''
    deprecated_minion = kwargs.get('minion', None)
    if tgt is None and deprecated_minion is None:
        log.warn("DEPRECATION WARNING: {0}".format(deprecation_warning))
        tgt = '*'  # targat all minions for backward compatibility
    elif tgt is None and isinstance(deprecated_minion, string_types):
        log.warn("DEPRECATION WARNING: {0}".format(deprecation_warning))
        tgt = deprecated_minion
    elif tgt is None:
        return {}
    pillar_util = salt.utils.master.MasterPillarUtil(tgt, expr_form,
                                                use_cached_grains=False,
                                                grains_fallback=False,
                                                use_cached_pillar=False,
                                                pillar_fallback=False,
                                                opts=__opts__)
    cached_mine = pillar_util.get_cached_mine_data()
    salt.output.display_output(cached_mine, None, __opts__)


def _clear_cache(tgt=None,
                 expr_form='glob',
                 clear_pillar=False,
                 clear_grains=False,
                 clear_mine=False,
                 clear_mine_func=None):
    '''
    Clear the cached data/files for the targeted minions.
    '''
    if tgt is None:
        return False
    pillar_util = salt.utils.master.MasterPillarUtil(tgt, expr_form,
                                            use_cached_grains=True,
                                            grains_fallback=False,
                                            use_cached_pillar=True,
                                            pillar_fallback=False,
                                            opts=__opts__)
    return pillar_util.clear_cached_minion_data(clear_pillar=clear_pillar,
                                                clear_grains=clear_grains,
                                                clear_mine=clear_mine,
                                                clear_mine_func=clear_mine_func)


def clear_pillar(tgt=None, expr_form='glob'):
    '''
    Clear the cached pillar data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_pillar
    '''
    return _clear_cache(tgt, expr_form, clear_pillar=True)


def clear_grains(tgt=None, expr_form='glob'):
    '''
    Clear the cached grains data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_grains
    '''
    return _clear_cache(tgt, expr_form, clear_grains=True)


def clear_mine(tgt=None, expr_form='glob'):
    '''
    Clear the cached mine data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_mine
    '''
    return _clear_cache(tgt, expr_form, clear_mine=True)


def clear_mine_func(tgt=None, expr_form='glob', clear_mine_func=None):
    '''
    Clear the cached mine function data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_mine_func tgt='*' clear_mine_func='network.interfaces'
    '''
    return _clear_cache(tgt, expr_form, clear_mine_func=clear_mine_func)


def clear_all(tgt=None, expr_form='glob'):
    '''
    Clear the cached pillar, grains, and mine data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_all
    '''
    return _clear_cache(tgt,
                        expr_form,
                        clear_pillar=True,
                        clear_grains=True,
                        clear_mine=True)
