# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "spm" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def pkgdb(opts):
    '''
    Return modules for SPM's package database

    .. versionadded:: 2015.8.0
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(
            opts,
            'pkgdb',
            base_path=__this_dir__,
        ),
        opts,
        tag='pkgdb'
    )


@loader_pre.LoaderFunc
def pkgfiles(opts):
    '''
    Return modules for SPM's file handling

    .. versionadded:: 2015.8.0
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(
            opts,
            'pkgfiles',
            base_path=__this_dir__,
        ),
        opts,
        tag='pkgfiles'
    )
