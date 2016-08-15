# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "wheel" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def wheels(opts, whitelist=None):
    '''
    Returns the wheels modules
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'wheel'),
        opts,
        tag='wheel',
        whitelist=whitelist,
    )
