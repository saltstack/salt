# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "client/ssh" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def ssh_wrapper(opts, functions=None, context=None):
    '''
    Returns the custom logging handler modules
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(
            opts,
            'wrapper',
            base_path=__this_dir__,
        ),
        opts,
        tag='wrapper',
        pack={
            '__salt__': functions,
            '__grains__': opts.get('grains', {}),
            '__pillar__': opts.get('pillar', {}),
            '__context__': context,
            },
    )
