# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "queues" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def queues(opts):
    '''
    Directly call a function inside a loader directory
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'queues', 'queue', ext_type_dirs='queue_dirs'),
        opts,
        tag='queues',
    )
