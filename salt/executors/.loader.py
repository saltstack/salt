# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "executors" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def executors(opts, functions=None, context=None):
    '''
    Returns the executor modules
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'executors', 'executor'),
        opts,
        tag='executor',
        pack={'__salt__': functions, '__context__': context or {}},
    )
