# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "returners" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def returners(opts, functions, whitelist=None, context=None):
    '''
    Returns the returner modules
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'returners', 'returner'),
        opts,
        tag='returner',
        whitelist=whitelist,
        pack={'__salt__': functions, '__context__': context},
    )
