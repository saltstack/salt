# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "tops" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def tops(opts):
    '''
    Returns the tops modules
    '''
    if 'master_tops' not in opts:
        return {}
    whitelist = list(opts['master_tops'].keys())
    ret = loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'tops', 'top'),
        opts,
        tag='top',
        whitelist=whitelist,
    )
    return loader_core.FilterDictWrapper(ret, '.top')
