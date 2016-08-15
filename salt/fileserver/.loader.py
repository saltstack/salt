# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "fileserver" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def fileserver(opts, backends):
    '''
    Returns the file server modules
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'fileserver'),
        opts,
        tag='fileserver',
        whitelist=backends,
    )
