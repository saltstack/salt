# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "renderers" sub-system'''


from __future__ import absolute_import

import logging

from salt import loader_core
from salt import loader_pre
from salt import template


LOG = logging.getLogger(__name__)


@loader_pre.LoaderFunc
def render(opts, functions, states=None):
    '''
    Returns the render modules
    '''
    pack = {'__salt__': functions,
            '__grains__': opts.get('grains', {})}
    if states:
        pack['__states__'] = states
    ret = loader_core.LazyLoader(
        loader_core.module_dirs(
            opts,
            'renderers',
            'render',
            ext_type_dirs='render_dirs',
        ),
        opts,
        tag='render',
        pack=pack,
    )
    rend = loader_core.FilterDictWrapper(ret, '.render')

    if not template.check_render_pipe_str(
            opts['renderer'], rend, opts['renderer_blacklist'], opts['renderer_whitelist']
    ):
        err = ('The renderer {0} is unavailable, this error is often because '
               'the needed software is unavailable'.format(opts['renderer']))
        LOG.critical(err)
        raise loader_core.LoaderError(err)
    return rend
