# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "grains" sub-system'''


# Import python libs
from __future__ import absolute_import
import logging
import os
import time

# Import 3rd-party libs
import salt.ext.six as six

# Import salt libs
import salt
from salt import loader_core
from salt import loader_pre
from salt.utils import is_proxy


log = logging.getLogger(__name__)


@loader_pre.LoaderFunc
def grain_funcs(opts, proxy=None):
    '''
    Returns the grain functions

      .. code-block:: python

          import salt.config
          import salt.loader

          __opts__ = salt.config.minion_config('/etc/salt/minion')
          grainfuncs = salt.loader.grain_funcs(__opts__)
    '''
    return loader_core.LazyLoader(
        loader_core.module_dirs(
            opts,
            'grains',
            'grain',
            ext_type_dirs='grains_dirs',
        ),
        opts,
        tag='grains',
    )


@loader_pre.LoaderFunc
def grains(opts, force_refresh=False, proxy=None):
    '''
    Return the functions for the dynamic grains and the values for the static
    grains.

    Since grains are computed early in the startup process, grains functions
    do not have __salt__ or __proxy__ available.  At proxy-minion startup,
    this function is called with the proxymodule LazyLoader object so grains
    functions can communicate with their controlled device.

    .. code-block:: python

        import salt.config
        import salt.loader

        __opts__ = salt.config.minion_config('/etc/salt/minion')
        __grains__ = salt.loader.grains(__opts__)
        print __grains__['id']
    '''
    # if we hae no grains, lets try loading from disk (TODO: move to decorator?)
    cfn = os.path.join(
        opts['cachedir'],
        'grains.cache.p'
    )
    if not force_refresh:
        if opts.get('grains_cache', False):
            if os.path.isfile(cfn):
                grains_cache_age = int(time.time() - os.path.getmtime(cfn))
                if opts.get('grains_cache_expiration', 300) >= grains_cache_age and not \
                        opts.get('refresh_grains_cache', False) and not force_refresh:
                    log.debug('Retrieving grains from cache')
                    try:
                        serial = salt.payload.Serial(opts)
                        with salt.utils.fopen(cfn, 'rb') as fp_:
                            cached_grains = serial.load(fp_)
                        return cached_grains
                    except (IOError, OSError):
                        pass
                else:
                    if force_refresh:
                        log.debug('Grains refresh requested. Refreshing grains.')
                    else:
                        log.debug('Grains cache last modified {0} seconds ago and '
                                  'cache expiration is set to {1}. '
                                  'Grains cache expired. Refreshing.'.format(
                                      grains_cache_age,
                                      opts.get('grains_cache_expiration', 300)
                                  ))
            else:
                log.debug('Grains cache file does not exist.')

    if opts.get('skip_grains', False):
        return {}
    grains_deep_merge = opts.get('grains_deep_merge', False) is True
    if 'conf_file' in opts:
        pre_opts = {}
        pre_opts.update(salt.config.load_config(
            opts['conf_file'], 'SALT_MINION_CONFIG',
            salt.config.DEFAULT_MINION_OPTS['conf_file']
        ))
        default_include = pre_opts.get(
            'default_include', opts['default_include']
        )
        include = pre_opts.get('include', [])
        pre_opts.update(salt.config.include_config(
            default_include, opts['conf_file'], verbose=False
        ))
        pre_opts.update(salt.config.include_config(
            include, opts['conf_file'], verbose=True
        ))
        if 'grains' in pre_opts:
            opts['grains'] = pre_opts['grains']
        else:
            opts['grains'] = {}
    else:
        opts['grains'] = {}

    grains_data = {}
    funcs = grain_funcs(opts, proxy=proxy)
    if force_refresh:  # if we refresh, lets reload grain modules
        funcs.clear()
    # Run core grains
    for key, fun in six.iteritems(funcs):
        if not key.startswith('core.'):
            continue
        log.trace('Loading {0} grain'.format(key))
        ret = fun()
        if not isinstance(ret, dict):
            continue
        if grains_deep_merge:
            salt.utils.dictupdate.update(grains_data, ret)
        else:
            grains_data.update(ret)

    # Run the rest of the grains
    for key, fun in six.iteritems(funcs):
        if key.startswith('core.') or key == '_errors':
            continue
        try:
            # Grains are loaded too early to take advantage of the injected
            # __proxy__ variable.  Pass an instance of that LazyLoader
            # here instead to grains functions if the grains functions take
            # one parameter.  Then the grains can have access to the
            # proxymodule for retrieving information from the connected
            # device.
            if fun.__code__.co_argcount == 1:
                ret = fun(proxy)
            else:
                ret = fun()
        except Exception:
            if is_proxy():
                log.info(
                    'The following CRITICAL message may not be an error;'
                    ' the proxy may not be completely established yet.'
                )
            log.critical(
                'Failed to load grains defined in grain file {0} in '
                'function {1}, error:\n'.format(
                    key, fun
                ),
                exc_info=True
            )
            continue
        if not isinstance(ret, dict):
            continue
        if grains_deep_merge:
            salt.utils.dictupdate.update(grains_data, ret)
        else:
            grains_data.update(ret)

    if opts.get('proxy_merge_grains_in_module', False) and proxy:
        try:
            proxytype = proxy.opts['proxy']['proxytype']
            if proxytype+'.grains' in proxy:
                if proxytype+'.initialized' in proxy and proxy[proxytype+'.initialized']():
                    try:
                        proxytype = proxy.opts['proxy']['proxytype']
                        ret = proxy[proxytype+'.grains']()
                        if grains_deep_merge:
                            salt.utils.dictupdate.update(grains_data, ret)
                        else:
                            grains_data.update(ret)
                    except Exception:
                        log.critical('Failed to run proxy\'s grains function!',
                            exc_info=True
                        )
        except KeyError:
            pass

    grains_data.update(opts['grains'])
    # Write cache if enabled
    if opts.get('grains_cache', False):
        cumask = os.umask(0o77)
        try:
            if salt.utils.is_windows():
                # Make sure cache file isn't read-only
                __salt__['cmd.run']('attrib -R "{0}"'.format(cfn))
            with salt.utils.fopen(cfn, 'w+b') as fp_:
                try:
                    serial = salt.payload.Serial(opts)
                    serial.dump(grains_data, fp_)
                except TypeError:
                    # Can't serialize pydsl
                    pass
        except (IOError, OSError):
            msg = 'Unable to write to grains cache file {0}'
            log.error(msg.format(cfn))
        os.umask(cumask)

    if grains_deep_merge:
        salt.utils.dictupdate.update(grains_data, opts['grains'])
    else:
        grains_data.update(opts['grains'])
    return grains_data
