# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "log" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def log_handlers(opts):
    '''
    Returns the custom logging handler modules

    :param dict opts: The Salt options dictionary
    '''
    ret = loader_core.LazyLoader(
        loader_core.module_dirs(
            opts,
            'log_handlers',
            int_type='handlers',
            base_path=__this_dir__,
        ),
        opts,
        tag='log_handlers',
    )
    return loader_core.FilterDictWrapper(ret, '.setup_handlers')
