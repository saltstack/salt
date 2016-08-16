# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "sdb" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def sdb(opts, functions=None, whitelist=None):
    '''
    Make a very small database call
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'sdb'),
        opts,
        tag='sdb',
        pack={'__sdb__': functions},
        whitelist=whitelist,
    )
