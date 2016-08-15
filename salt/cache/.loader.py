# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "engines" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def cache(opts, serial):
    '''
    Returns the returner modules
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'cache', 'cache'),
        opts,
        tag='cache',
        pack={'__opts__': opts, '__context__': {'serial': serial}},
    )
