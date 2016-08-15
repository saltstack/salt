# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "search" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def search(opts, returners, whitelist=None):
    '''
    Returns the search modules

    :param dict opts: The Salt options dictionary
    :param returners: Undocumented
    :param whitelist: Undocumented
    '''
    # TODO Document returners arg
    # TODO Document whitelist arg
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'search', 'search'),
        opts,
        tag='search',
        whitelist=whitelist,
        pack={'__ret__': returners},
    )
