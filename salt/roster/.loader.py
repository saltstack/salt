# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "roster" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def roster(opts, whitelist=None):
    '''
    Returns the roster modules
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'roster'),
        opts,
        tag='roster',
        whitelist=whitelist,
    )
