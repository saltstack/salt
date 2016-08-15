# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "pillar" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def pillars(opts, functions, context=None):
    '''
    Returns the pillars modules
    '''
    ret = loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'pillar'),
        opts,
        tag='pillar',
        pack={'__salt__': functions, '__context__': context},
    )
    ret.pack['__ext_pillar__'] = ret
    return loader_core.FilterDictWrapper(ret, '.ext_pillar')
