# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "runners" sub-system'''


from __future__ import absolute_import

from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def runner(opts, utils=None):
    '''
    Directly call a function inside a loader directory
    '''
    if utils is None:
        utils = {}
    ret = loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'runners', 'runner', ext_type_dirs='runner_dirs'),
        opts,
        tag='runners',
        pack={'__utils__': utils},
    )
    # TODO: change from __salt__ to something else, we overload __salt__ too much
    ret.pack['__salt__'] = ret
    return ret
