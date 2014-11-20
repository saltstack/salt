# -*- coding: utf-8 -*-
'''
Return cached data from minions
'''
from __future__ import absolute_import
# Import python libs
import logging

# Import salt libs
import salt.log
import salt.utils.master
import salt.payload
from salt.ext.six import string_types

log = logging.getLogger(__name__)

DEPRECATION_WARNING = ("The 'minion' arg will be removed from "
                       "cache.py runner. Specify minion with 'tgt' arg!")


def grains(tgt=None, expr_form='glob', outputter=None, **kwargs):
    '''
    Return cached grains of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.grains
    '''
    deprecated_minion = kwargs.get('minion', None)
    if tgt is None and deprecated_minion is None:
        log.warn("DEPRECATION WARNING: {0}".format(DEPRECATION_WARNING))
        tgt = '*'  # targat all minions for backward compatibility
    elif tgt is None and isinstance(deprecated_minion, string_types):
        log.warn("DEPRECATION WARNING: {0}".format(DEPRECATION_WARNING))
        tgt = deprecated_minion
    elif tgt is None:
        return {}
    pillar_util = salt.utils.master.MasterPillarUtil(tgt, expr_form,
                                                     use_cached_grains=True,
                                                     grains_fallback=False,
                                                     opts=__opts__)
    cached_grains = pillar_util.get_minion_grains()
    if outputter:
        return {'outputter': outputter, 'data': cached_grains}
    else:
        return cached_grains


def pillar(tgt=None, expr_form='glob', outputter=None, **kwargs):
    '''
    Return cached pillars of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.pillar
    '''
    deprecated_minion = kwargs.get('minion', None)
    if tgt is None and deprecated_minion is None:
        log.warn("DEPRECATION WARNING: {0}".format(DEPRECATION_WARNING))
        tgt = '*'  # targat all minions for backward compatibility
    elif tgt is None and isinstance(deprecated_minion, string_types):
        log.warn("DEPRECATION WARNING: {0}".format(DEPRECATION_WARNING))
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
    if outputter:
        return {'outputter': outputter, 'data': cached_pillar}
    else:
        return cached_pillar


def mine(tgt=None, expr_form='glob', outputter=None, **kwargs):
    '''
    Return cached mine data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.mine
    '''
    deprecated_minion = kwargs.get('minion', None)
    if tgt is None and deprecated_minion is None:
        log.warn("DEPRECATION WARNING: {0}".format(DEPRECATION_WARNING))
        tgt = '*'  # targat all minions for backward compatibility
    elif tgt is None and isinstance(deprecated_minion, string_types):
        log.warn("DEPRECATION WARNING: {0}".format(DEPRECATION_WARNING))
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
    if outputter:
        return {'outputter': outputter, 'data': cached_mine}
    else:
        return cached_mine


def _clear_cache(tgt=None,
                 expr_form='glob',
                 clear_pillar_flag=False,
                 clear_grains_flag=False,
                 clear_mine_flag=False,
                 clear_mine_func_flag=None):
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
    return pillar_util.clear_cached_minion_data(clear_pillar=clear_pillar_flag,
                                                clear_grains=clear_grains_flag,
                                                clear_mine=clear_mine_flag,
                                                clear_mine_func=clear_mine_func_flag)


def clear_pillar(tgt=None, expr_form='glob'):
    '''
    Clear the cached pillar data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_pillar
    '''
    return _clear_cache(tgt, expr_form, clear_pillar_flag=True)


def clear_grains(tgt=None, expr_form='glob'):
    '''
    Clear the cached grains data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_grains
    '''
    return _clear_cache(tgt, expr_form, clear_grains_flag=True)


def clear_mine(tgt=None, expr_form='glob'):
    '''
    Clear the cached mine data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_mine
    '''
    return _clear_cache(tgt, expr_form, clear_mine_flag=True)


def clear_mine_func(tgt=None, expr_form='glob', clear_mine_func_flag=None):
    '''
    Clear the cached mine function data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_mine_func tgt='*' clear_mine_func='network.interfaces'
    '''
    return _clear_cache(tgt, expr_form, clear_mine_func_flag=clear_mine_func_flag)


def clear_all(tgt=None, expr_form='glob'):
    '''
    Clear the cached pillar, grains, and mine data of the targeted minions

    CLI Example:

    .. code-block:: bash

        salt-run cache.clear_all
    '''
    return _clear_cache(tgt,
                        expr_form,
                        clear_pillar_flag=True,
                        clear_grains_flag=True,
                        clear_mine_flag=True)
