# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "auth" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def auth(opts, whitelist=None):
    '''
    Returns the auth modules

    :param dict opts: The Salt options dictionary
    :returns: LazyLoader
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'auth'),
        opts,
        tag='auth',
        whitelist=whitelist,
        pack={'__salt__': minion_mods(opts)},
    )
