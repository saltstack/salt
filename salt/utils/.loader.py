# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "utils" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def utils(opts, whitelist=None, context=None):
    '''
    Returns the utility modules
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'utils', ext_type_dirs='utils_dirs'),
        opts,
        tag='utils',
        whitelist=whitelist,
        pack={'__context__': context},
    )
