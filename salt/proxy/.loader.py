# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "proxy" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def proxy(opts, functions=None, returners=None, whitelist=None):
    '''
    Returns the proxy module for this salt-proxy-minion
    '''
    ret = loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'proxy'),
        opts,
        tag='proxy',
        pack={'__salt__': functions, '__ret__': returners},
    )

    ret.pack['__proxy__'] = ret

    return ret
