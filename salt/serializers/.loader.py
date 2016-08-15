# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "serializers" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def serializers(opts):
    '''
    Returns the serializers modules
    :param dict opts: The Salt options dictionary
    :returns: loader_core.LazyLoader instance, with only serializers present in the keyspace
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'serializers'),
        opts,
        tag='serializers',
    )
