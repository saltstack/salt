# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "thorium" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def thorium(opts, functions, runners):
    '''
    Load the thorium runtime modules
    '''
    pack = {'__salt__': functions, '__runner__': runners, '__context__': {}}
    ret = loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'thorium'),
        opts,
        tag='thorium',
        pack=pack)
    ret.pack['__thorium__'] = ret
    return ret
