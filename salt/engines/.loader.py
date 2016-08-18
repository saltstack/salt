# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "engines" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def engines(opts, functions, runners, proxy=None):
    '''
    Return the master services plugins
    '''
    pack = {'__salt__': functions,
            '__runners__': runners,
            '__proxy__': proxy}
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'engines'),
        opts,
        tag='engines',
        pack=pack,
    )
