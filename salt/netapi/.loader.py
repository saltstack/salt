# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "netapi" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def netapi(opts):
    '''
    Return the network api functions
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'netapi'),
        opts,
        tag='netapi',
    )
