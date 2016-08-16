# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "beacons" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def beacons(opts, functions, context=None):
    '''
    Load the beacon modules

    :param dict opts: The Salt options dictionary
    :param dict functions: A dictionary of minion modules, with module names as
                            keys and funcs as values.
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'beacons'),
        opts,
        tag='beacons',
        pack={'__context__': context, '__salt__': functions},
    )
