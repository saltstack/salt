# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "output" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def outputters(opts):
    '''
    Returns the outputters modules

    :param dict opts: The Salt options dictionary
    :returns: loader_core.LazyLoader instance, with only outputters present in the keyspace
    '''
    ret = loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'output', ext_type_dirs='outputter_dirs'),
        opts,
        tag='output',
    )
    wrapped_ret = loader_core.FilterDictWrapper(ret, '.output')
    # TODO: this name seems terrible... __salt__ should always be execution mods
    ret.pack['__salt__'] = wrapped_ret
    return wrapped_ret
