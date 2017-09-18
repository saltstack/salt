# -*- coding: utf-8 -*-
'''
The Salt loader is the core to Salt's plugin system, the loader scans
directories for python loadable code and organizes the code into the
plugin interfaces used by Salt.
'''

# Import python libs
from __future__ import absolute_import
import os
import sys
import time
import logging
import inspect
import tempfile
import functools
import types
from collections import MutableMapping
from zipimport import zipimporter

# Import salt libs
import salt.config
import salt.syspaths
import salt.utils.context
import salt.utils.dictupdate
import salt.utils.event
import salt.utils.files
import salt.utils.lazy
import salt.utils.odict
import salt.utils.platform
import salt.utils.versions
from salt.exceptions import LoaderError
from salt.template import check_render_pipe_str
from salt.utils.decorators import Depends

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import reload_module

if sys.version_info[:2] >= (3, 5):
    import importlib.machinery  # pylint: disable=no-name-in-module,import-error
    import importlib.util  # pylint: disable=no-name-in-module,import-error
    USE_IMPORTLIB = True
else:
    import imp
    USE_IMPORTLIB = False

try:
    import pkg_resources
    HAS_PKG_RESOURCES = True
except ImportError:
    HAS_PKG_RESOURCES = False

log = logging.getLogger(__name__)

SALT_BASE_PATH = os.path.abspath(salt.syspaths.INSTALL_DIR)
LOADED_BASE_NAME = u'salt.loaded'

if USE_IMPORTLIB:
    # pylint: disable=no-member
    MODULE_KIND_SOURCE = 1
    MODULE_KIND_COMPILED = 2
    MODULE_KIND_EXTENSION = 3
    MODULE_KIND_PKG_DIRECTORY = 5
    SUFFIXES = []
    for suffix in importlib.machinery.EXTENSION_SUFFIXES:
        SUFFIXES.append((suffix, u'rb', MODULE_KIND_EXTENSION))
    for suffix in importlib.machinery.BYTECODE_SUFFIXES:
        SUFFIXES.append((suffix, u'rb', MODULE_KIND_COMPILED))
    for suffix in importlib.machinery.SOURCE_SUFFIXES:
        SUFFIXES.append((suffix, u'rb', MODULE_KIND_SOURCE))
    MODULE_KIND_MAP = {
        MODULE_KIND_SOURCE: importlib.machinery.SourceFileLoader,
        MODULE_KIND_COMPILED: importlib.machinery.SourcelessFileLoader,
        MODULE_KIND_EXTENSION: importlib.machinery.ExtensionFileLoader
    }
    # pylint: enable=no-member
else:
    SUFFIXES = imp.get_suffixes()

# Because on the cloud drivers we do `from salt.cloud.libcloudfuncs import *`
# which simplifies code readability, it adds some unsupported functions into
# the driver's module scope.
# We list un-supported functions here. These will be removed from the loaded.
#  TODO:  remove the need for this cross-module code. Maybe use NotImplemented
LIBCLOUD_FUNCS_NOT_SUPPORTED = (
    u'parallels.avail_sizes',
    u'parallels.avail_locations',
    u'proxmox.avail_sizes',
    u'rackspace.reboot',
    u'openstack.list_locations',
    u'rackspace.list_locations'
)

# Will be set to pyximport module at runtime if cython is enabled in config.
pyximport = None


def static_loader(
        opts,
        ext_type,
        tag,
        pack=None,
        int_type=None,
        ext_dirs=True,
        ext_type_dirs=None,
        base_path=None,
        filter_name=None,
        ):
    funcs = LazyLoader(
        _module_dirs(
            opts,
            ext_type,
            tag,
            int_type,
            ext_dirs,
            ext_type_dirs,
            base_path,
        ),
        opts,
        tag=tag,
        pack=pack,
    )
    ret = {}
    funcs._load_all()
    if filter_name:
        funcs = FilterDictWrapper(funcs, filter_name)
    for key in funcs:
        ret[key] = funcs[key]
    return ret


def _module_dirs(
        opts,
        ext_type,
        tag=None,
        int_type=None,
        ext_dirs=True,
        ext_type_dirs=None,
        base_path=None,
        ):
    if tag is None:
        tag = ext_type
    sys_types = os.path.join(base_path or SALT_BASE_PATH, int_type or ext_type)
    ext_types = os.path.join(opts[u'extension_modules'], ext_type)

    ext_type_types = []
    if ext_dirs:
        if ext_type_dirs is None:
            ext_type_dirs = u'{0}_dirs'.format(tag)
        if ext_type_dirs in opts:
            ext_type_types.extend(opts[ext_type_dirs])
        if HAS_PKG_RESOURCES and ext_type_dirs:
            for entry_point in pkg_resources.iter_entry_points(u'salt.loader', ext_type_dirs):
                loaded_entry_point = entry_point.load()
                for path in loaded_entry_point():
                    ext_type_types.append(path)

    cli_module_dirs = []
    # The dirs can be any module dir, or a in-tree _{ext_type} dir
    for _dir in opts.get(u'module_dirs', []):
        # Prepend to the list to match cli argument ordering
        maybe_dir = os.path.join(_dir, ext_type)
        if os.path.isdir(maybe_dir):
            cli_module_dirs.insert(0, maybe_dir)
            continue

        maybe_dir = os.path.join(_dir, u'_{0}'.format(ext_type))
        if os.path.isdir(maybe_dir):
            cli_module_dirs.insert(0, maybe_dir)

    return cli_module_dirs + ext_type_types + [ext_types, sys_types]


def minion_mods(
        opts,
        context=None,
        utils=None,
        whitelist=None,
        initial_load=False,
        loaded_base_name=None,
        notify=False,
        static_modules=None,
        proxy=None):
    '''
    Load execution modules

    Returns a dictionary of execution modules appropriate for the current
    system by evaluating the __virtual__() function in each module.

    :param dict opts: The Salt options dictionary

    :param dict context: A Salt context that should be made present inside
                            generated modules in __context__

    :param dict utils: Utility functions which should be made available to
                            Salt modules in __utils__. See `utils_dirs` in
                            salt.config for additional information about
                            configuration.

    :param list whitelist: A list of modules which should be whitelisted.
    :param bool initial_load: Deprecated flag! Unused.
    :param str loaded_base_name: A string marker for the loaded base name.
    :param bool notify: Flag indicating that an event should be fired upon
                        completion of module loading.

    .. code-block:: python

        import salt.config
        import salt.loader

        __opts__ = salt.config.minion_config('/etc/salt/minion')
        __grains__ = salt.loader.grains(__opts__)
        __opts__['grains'] = __grains__
        __utils__ = salt.loader.utils(__opts__)
        __salt__ = salt.loader.minion_mods(__opts__, utils=__utils__)
        __salt__['test.ping']()
    '''
    # TODO Publish documentation for module whitelisting
    if not whitelist:
        whitelist = opts.get(u'whitelist_modules', None)
    ret = LazyLoader(
        _module_dirs(opts, u'modules', u'module'),
        opts,
        tag=u'module',
        pack={u'__context__': context, u'__utils__': utils, u'__proxy__': proxy},
        whitelist=whitelist,
        loaded_base_name=loaded_base_name,
        static_modules=static_modules,
    )

    ret.pack[u'__salt__'] = ret

    # Load any provider overrides from the configuration file providers option
    #  Note: Providers can be pkg, service, user or group - not to be confused
    #        with cloud providers.
    providers = opts.get(u'providers', False)
    if providers and isinstance(providers, dict):
        for mod in providers:
            # sometimes providers opts is not to diverge modules but
            # for other configuration
            try:
                funcs = raw_mod(opts, providers[mod], ret)
            except TypeError:
                break
            else:
                if funcs:
                    for func in funcs:
                        f_key = u'{0}{1}'.format(mod, func[func.rindex(u'.'):])
                        ret[f_key] = funcs[func]

    if notify:
        evt = salt.utils.event.get_event(u'minion', opts=opts, listen=False)
        evt.fire_event({u'complete': True}, tag=u'/salt/minion/minion_mod_complete')

    return ret


def raw_mod(opts, name, functions, mod=u'modules'):
    '''
    Returns a single module loaded raw and bypassing the __virtual__ function

    .. code-block:: python

        import salt.config
        import salt.loader

        __opts__ = salt.config.minion_config('/etc/salt/minion')
        testmod = salt.loader.raw_mod(__opts__, 'test', None)
        testmod['test.ping']()
    '''
    loader = LazyLoader(
        _module_dirs(opts, mod, u'module'),
        opts,
        tag=u'rawmodule',
        virtual_enable=False,
        pack={u'__salt__': functions},
    )
    # if we don't have the module, return an empty dict
    if name not in loader.file_mapping:
        return {}

    loader._load_module(name)  # load a single module (the one passed in)
    return dict(loader._dict)  # return a copy of *just* the funcs for `name`


def engines(opts, functions, runners, utils, proxy=None):
    '''
    Return the master services plugins
    '''
    pack = {u'__salt__': functions,
            u'__runners__': runners,
            u'__proxy__': proxy,
            u'__utils__': utils}
    return LazyLoader(
        _module_dirs(opts, u'engines'),
        opts,
        tag=u'engines',
        pack=pack,
    )


def proxy(opts, functions=None, returners=None, whitelist=None, utils=None):
    '''
    Returns the proxy module for this salt-proxy-minion
    '''
    ret = LazyLoader(
        _module_dirs(opts, u'proxy'),
        opts,
        tag=u'proxy',
        pack={u'__salt__': functions, u'__ret__': returners, u'__utils__': utils},
    )

    ret.pack[u'__proxy__'] = ret

    return ret


def returners(opts, functions, whitelist=None, context=None, proxy=None):
    '''
    Returns the returner modules
    '''
    return LazyLoader(
        _module_dirs(opts, u'returners', u'returner'),
        opts,
        tag=u'returner',
        whitelist=whitelist,
        pack={u'__salt__': functions, u'__context__': context, u'__proxy__': proxy or {}},
    )


def utils(opts, whitelist=None, context=None, proxy=proxy):
    '''
    Returns the utility modules
    '''
    return LazyLoader(
        _module_dirs(opts, u'utils', ext_type_dirs=u'utils_dirs'),
        opts,
        tag=u'utils',
        whitelist=whitelist,
        pack={u'__context__': context, u'__proxy__': proxy or {}},
    )


def pillars(opts, functions, context=None):
    '''
    Returns the pillars modules
    '''
    ret = LazyLoader(_module_dirs(opts, u'pillar'),
                     opts,
                     tag=u'pillar',
                     pack={u'__salt__': functions,
                           u'__context__': context,
                           u'__utils__': utils(opts)})
    ret.pack[u'__ext_pillar__'] = ret
    return FilterDictWrapper(ret, u'.ext_pillar')


def tops(opts):
    '''
    Returns the tops modules
    '''
    if u'master_tops' not in opts:
        return {}
    whitelist = list(opts[u'master_tops'].keys())
    ret = LazyLoader(
        _module_dirs(opts, u'tops', u'top'),
        opts,
        tag=u'top',
        whitelist=whitelist,
    )
    return FilterDictWrapper(ret, u'.top')


def wheels(opts, whitelist=None):
    '''
    Returns the wheels modules
    '''
    return LazyLoader(
        _module_dirs(opts, u'wheel'),
        opts,
        tag=u'wheel',
        whitelist=whitelist,
    )


def outputters(opts):
    '''
    Returns the outputters modules

    :param dict opts: The Salt options dictionary
    :returns: LazyLoader instance, with only outputters present in the keyspace
    '''
    ret = LazyLoader(
        _module_dirs(opts, u'output', ext_type_dirs=u'outputter_dirs'),
        opts,
        tag=u'output',
    )
    wrapped_ret = FilterDictWrapper(ret, u'.output')
    # TODO: this name seems terrible... __salt__ should always be execution mods
    ret.pack[u'__salt__'] = wrapped_ret
    return wrapped_ret


def serializers(opts):
    '''
    Returns the serializers modules
    :param dict opts: The Salt options dictionary
    :returns: LazyLoader instance, with only serializers present in the keyspace
    '''
    return LazyLoader(
        _module_dirs(opts, u'serializers'),
        opts,
        tag=u'serializers',
    )


def eauth_tokens(opts):
    '''
    Returns the tokens modules
    :param dict opts: The Salt options dictionary
    :returns: LazyLoader instance, with only token backends present in the keyspace
    '''
    return LazyLoader(
        _module_dirs(opts, 'tokens'),
        opts,
        tag='tokens',
    )


def auth(opts, whitelist=None):
    '''
    Returns the auth modules

    :param dict opts: The Salt options dictionary
    :returns: LazyLoader
    '''
    return LazyLoader(
        _module_dirs(opts, u'auth'),
        opts,
        tag=u'auth',
        whitelist=whitelist,
        pack={u'__salt__': minion_mods(opts)},
    )


def fileserver(opts, backends):
    '''
    Returns the file server modules
    '''
    return LazyLoader(_module_dirs(opts, u'fileserver'),
                      opts,
                      tag=u'fileserver',
                      whitelist=backends,
                      pack={u'__utils__': utils(opts)})


def roster(opts, runner, whitelist=None):
    '''
    Returns the roster modules
    '''
    return LazyLoader(
        _module_dirs(opts, u'roster'),
        opts,
        tag=u'roster',
        whitelist=whitelist,
        pack={u'__runner__': runner},
    )


def thorium(opts, functions, runners):
    '''
    Load the thorium runtime modules
    '''
    pack = {u'__salt__': functions, u'__runner__': runners, u'__context__': {}}
    ret = LazyLoader(_module_dirs(opts, u'thorium'),
            opts,
            tag=u'thorium',
            pack=pack)
    ret.pack[u'__thorium__'] = ret
    return ret


def states(opts, functions, utils, serializers, whitelist=None, proxy=None):
    '''
    Returns the state modules

    :param dict opts: The Salt options dictionary
    :param dict functions: A dictionary of minion modules, with module names as
                            keys and funcs as values.

    .. code-block:: python

        import salt.config
        import salt.loader

        __opts__ = salt.config.minion_config('/etc/salt/minion')
        statemods = salt.loader.states(__opts__, None, None)
    '''
    ret = LazyLoader(
        _module_dirs(opts, u'states'),
        opts,
        tag=u'states',
        pack={u'__salt__': functions, u'__proxy__': proxy or {}},
        whitelist=whitelist,
    )
    ret.pack[u'__states__'] = ret
    ret.pack[u'__utils__'] = utils
    ret.pack[u'__serializers__'] = serializers
    return ret


def beacons(opts, functions, context=None, proxy=None):
    '''
    Load the beacon modules

    :param dict opts: The Salt options dictionary
    :param dict functions: A dictionary of minion modules, with module names as
                            keys and funcs as values.
    '''
    return LazyLoader(
        _module_dirs(opts, u'beacons'),
        opts,
        tag=u'beacons',
        pack={u'__context__': context, u'__salt__': functions, u'__proxy__': proxy or {}},
        virtual_funcs=[],
    )


def log_handlers(opts):
    '''
    Returns the custom logging handler modules

    :param dict opts: The Salt options dictionary
    '''
    ret = LazyLoader(
        _module_dirs(
            opts,
            u'log_handlers',
            int_type=u'handlers',
            base_path=os.path.join(SALT_BASE_PATH, u'log'),
        ),
        opts,
        tag=u'log_handlers',
    )
    return FilterDictWrapper(ret, u'.setup_handlers')


def ssh_wrapper(opts, functions=None, context=None):
    '''
    Returns the custom logging handler modules
    '''
    return LazyLoader(
        _module_dirs(
            opts,
            u'wrapper',
            base_path=os.path.join(SALT_BASE_PATH, os.path.join(u'client', u'ssh')),
        ),
        opts,
        tag=u'wrapper',
        pack={
            u'__salt__': functions,
            u'__grains__': opts.get(u'grains', {}),
            u'__pillar__': opts.get(u'pillar', {}),
            u'__context__': context,
            },
    )


def render(opts, functions, states=None, proxy=None):
    '''
    Returns the render modules
    '''
    pack = {u'__salt__': functions,
            u'__grains__': opts.get(u'grains', {})}
    if states:
        pack[u'__states__'] = states
    pack[u'__proxy__'] = proxy or {}
    ret = LazyLoader(
        _module_dirs(
            opts,
            u'renderers',
            u'render',
            ext_type_dirs=u'render_dirs',
        ),
        opts,
        tag=u'render',
        pack=pack,
    )
    rend = FilterDictWrapper(ret, u'.render')

    if not check_render_pipe_str(opts[u'renderer'], rend, opts[u'renderer_blacklist'], opts[u'renderer_whitelist']):
        err = (u'The renderer {0} is unavailable, this error is often because '
               u'the needed software is unavailable'.format(opts[u'renderer']))
        log.critical(err)
        raise LoaderError(err)
    return rend


def grain_funcs(opts, proxy=None):
    '''
    Returns the grain functions

      .. code-block:: python

          import salt.config
          import salt.loader

          __opts__ = salt.config.minion_config('/etc/salt/minion')
          grainfuncs = salt.loader.grain_funcs(__opts__)
    '''
    return LazyLoader(
        _module_dirs(
            opts,
            u'grains',
            u'grain',
            ext_type_dirs=u'grains_dirs',
        ),
        opts,
        tag=u'grains',
    )


def _load_cached_grains(opts, cfn):
    '''
    Returns the grains cached in cfn, or None if the cache is too old or is
    corrupted.
    '''
    if not os.path.isfile(cfn):
        log.debug(u'Grains cache file does not exist.')
        return None

    grains_cache_age = int(time.time() - os.path.getmtime(cfn))
    if grains_cache_age > opts.get(u'grains_cache_expiration', 300):
        log.debug(
            u'Grains cache last modified %s seconds ago and cache '
            u'expiration is set to %s. Grains cache expired. '
            u'Refreshing.',
            grains_cache_age, opts.get(u'grains_cache_expiration', 300)
        )
        return None

    if opts.get(u'refresh_grains_cache', False):
        log.debug(u'refresh_grains_cache requested, Refreshing.')
        return None

    log.debug(u'Retrieving grains from cache')
    try:
        serial = salt.payload.Serial(opts)
        with salt.utils.files.fopen(cfn, u'rb') as fp_:
            cached_grains = serial.load(fp_)
        if not cached_grains:
            log.debug(u'Cached grains are empty, cache might be corrupted. Refreshing.')
            return None

        return cached_grains
    except (IOError, OSError):
        return None


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
    # Need to re-import salt.config, somehow it got lost when a minion is starting
    import salt.config
    # if we have no grains, lets try loading from disk (TODO: move to decorator?)
    cfn = os.path.join(
        opts[u'cachedir'],
        u'grains.cache.p'
    )
    if not force_refresh and opts.get(u'grains_cache', False):
        cached_grains = _load_cached_grains(opts, cfn)
        if cached_grains:
            return cached_grains
    else:
        log.debug(u'Grains refresh requested. Refreshing grains.')

    if opts.get(u'skip_grains', False):
        return {}
    grains_deep_merge = opts.get(u'grains_deep_merge', False) is True
    if u'conf_file' in opts:
        pre_opts = {}
        pre_opts.update(salt.config.load_config(
            opts[u'conf_file'], u'SALT_MINION_CONFIG',
            salt.config.DEFAULT_MINION_OPTS[u'conf_file']
        ))
        default_include = pre_opts.get(
            u'default_include', opts[u'default_include']
        )
        include = pre_opts.get(u'include', [])
        pre_opts.update(salt.config.include_config(
            default_include, opts[u'conf_file'], verbose=False
        ))
        pre_opts.update(salt.config.include_config(
            include, opts[u'conf_file'], verbose=True
        ))
        if u'grains' in pre_opts:
            opts[u'grains'] = pre_opts[u'grains']
        else:
            opts[u'grains'] = {}
    else:
        opts[u'grains'] = {}

    grains_data = {}
    funcs = grain_funcs(opts, proxy=proxy)
    if force_refresh:  # if we refresh, lets reload grain modules
        funcs.clear()
    # Run core grains
    for key in funcs:
        if not key.startswith(u'core.'):
            continue
        log.trace(u'Loading %s grain', key)
        ret = funcs[key]()
        if not isinstance(ret, dict):
            continue
        if grains_deep_merge:
            salt.utils.dictupdate.update(grains_data, ret)
        else:
            grains_data.update(ret)

    # Run the rest of the grains
    for key in funcs:
        if key.startswith(u'core.') or key == u'_errors':
            continue
        try:
            # Grains are loaded too early to take advantage of the injected
            # __proxy__ variable.  Pass an instance of that LazyLoader
            # here instead to grains functions if the grains functions take
            # one parameter.  Then the grains can have access to the
            # proxymodule for retrieving information from the connected
            # device.
            log.trace(u'Loading %s grain', key)
            if funcs[key].__code__.co_argcount == 1:
                ret = funcs[key](proxy)
            else:
                ret = funcs[key]()
        except Exception:
            if salt.utils.platform.is_proxy():
                log.info(u'The following CRITICAL message may not be an error; the proxy may not be completely established yet.')
            log.critical(
                u'Failed to load grains defined in grain file %s in '
                u'function %s, error:\n', key, funcs[key],
                exc_info=True
            )
            continue
        if not isinstance(ret, dict):
            continue
        if grains_deep_merge:
            salt.utils.dictupdate.update(grains_data, ret)
        else:
            grains_data.update(ret)

    if opts.get(u'proxy_merge_grains_in_module', True) and proxy:
        try:
            proxytype = proxy.opts[u'proxy'][u'proxytype']
            if proxytype + u'.grains' in proxy:
                if proxytype + u'.initialized' in proxy and proxy[proxytype + u'.initialized']():
                    try:
                        proxytype = proxy.opts[u'proxy'][u'proxytype']
                        ret = proxy[proxytype + u'.grains']()
                        if grains_deep_merge:
                            salt.utils.dictupdate.update(grains_data, ret)
                        else:
                            grains_data.update(ret)
                    except Exception:
                        log.critical(u'Failed to run proxy\'s grains function!',
                            exc_info=True
                        )
        except KeyError:
            pass

    grains_data.update(opts[u'grains'])
    # Write cache if enabled
    if opts.get(u'grains_cache', False):
        cumask = os.umask(0o77)
        try:
            if salt.utils.platform.is_windows():
                # Late import
                import salt.modules.cmdmod
                # Make sure cache file isn't read-only
                salt.modules.cmdmod._run_quiet(u'attrib -R "{0}"'.format(cfn))
            with salt.utils.files.fopen(cfn, u'w+b') as fp_:
                try:
                    serial = salt.payload.Serial(opts)
                    serial.dump(grains_data, fp_)
                except TypeError as e:
                    log.error(u'Failed to serialize grains cache: %s', e)
                    raise  # re-throw for cleanup
        except Exception as e:
            log.error(u'Unable to write to grains cache file %s: %s', cfn, e)
            # Based on the original exception, the file may or may not have been
            # created. If it was, we will remove it now, as the exception means
            # the serialized data is not to be trusted, no matter what the
            # exception is.
            if os.path.isfile(cfn):
                os.unlink(cfn)
        os.umask(cumask)

    if grains_deep_merge:
        salt.utils.dictupdate.update(grains_data, opts[u'grains'])
    else:
        grains_data.update(opts[u'grains'])
    return grains_data


# TODO: get rid of? Does anyone use this? You should use raw() instead
def call(fun, **kwargs):
    '''
    Directly call a function inside a loader directory
    '''
    args = kwargs.get(u'args', [])
    dirs = kwargs.get(u'dirs', [])

    funcs = LazyLoader(
        [os.path.join(SALT_BASE_PATH, u'modules')] + dirs,
        None,
        tag=u'modules',
        virtual_enable=False,
    )
    return funcs[fun](*args)


def runner(opts, utils=None):
    '''
    Directly call a function inside a loader directory
    '''
    if utils is None:
        utils = {}
    ret = LazyLoader(
        _module_dirs(opts, u'runners', u'runner', ext_type_dirs=u'runner_dirs'),
        opts,
        tag=u'runners',
        pack={u'__utils__': utils},
    )
    # TODO: change from __salt__ to something else, we overload __salt__ too much
    ret.pack[u'__salt__'] = ret
    return ret


def queues(opts):
    '''
    Directly call a function inside a loader directory
    '''
    return LazyLoader(
        _module_dirs(opts, u'queues', u'queue', ext_type_dirs=u'queue_dirs'),
        opts,
        tag=u'queues',
    )


def sdb(opts, functions=None, whitelist=None, utils=None):
    '''
    Make a very small database call
    '''
    if utils is None:
        utils = {}

    return LazyLoader(
        _module_dirs(opts, u'sdb'),
        opts,
        tag=u'sdb',
        pack={
            u'__sdb__': functions,
            u'__opts__': opts,
            u'__utils__': utils,
        },
        whitelist=whitelist,
    )


def pkgdb(opts):
    '''
    Return modules for SPM's package database

    .. versionadded:: 2015.8.0
    '''
    return LazyLoader(
        _module_dirs(
            opts,
            u'pkgdb',
            base_path=os.path.join(SALT_BASE_PATH, u'spm')
        ),
        opts,
        tag=u'pkgdb'
    )


def pkgfiles(opts):
    '''
    Return modules for SPM's file handling

    .. versionadded:: 2015.8.0
    '''
    return LazyLoader(
        _module_dirs(
            opts,
            u'pkgfiles',
            base_path=os.path.join(SALT_BASE_PATH, u'spm')
        ),
        opts,
        tag=u'pkgfiles'
    )


def clouds(opts):
    '''
    Return the cloud functions
    '''
    # Let's bring __active_provider_name__, defaulting to None, to all cloud
    # drivers. This will get temporarily updated/overridden with a context
    # manager when needed.
    functions = LazyLoader(
        _module_dirs(opts,
                     u'clouds',
                     u'cloud',
                     base_path=os.path.join(SALT_BASE_PATH, u'cloud'),
                     int_type=u'clouds'),
        opts,
        tag=u'clouds',
        pack={u'__utils__': salt.loader.utils(opts),
              u'__active_provider_name__': None},
    )
    for funcname in LIBCLOUD_FUNCS_NOT_SUPPORTED:
        log.trace(
            u'\'%s\' has been marked as not supported. Removing from the '
            u'list of supported cloud functions', funcname
        )
        functions.pop(funcname, None)
    return functions


def netapi(opts):
    '''
    Return the network api functions
    '''
    return LazyLoader(
        _module_dirs(opts, u'netapi'),
        opts,
        tag=u'netapi',
    )


def executors(opts, functions=None, context=None, proxy=None):
    '''
    Returns the executor modules
    '''
    return LazyLoader(
        _module_dirs(opts, u'executors', u'executor'),
        opts,
        tag=u'executor',
        pack={u'__salt__': functions, u'__context__': context or {}, u'__proxy__': proxy or {}},
    )


def cache(opts, serial):
    '''
    Returns the returner modules
    '''
    return LazyLoader(
        _module_dirs(opts, u'cache', u'cache'),
        opts,
        tag=u'cache',
        pack={u'__opts__': opts, u'__context__': {u'serial': serial}},
    )


def _generate_module(name):
    if name in sys.modules:
        return

    code = u"'''Salt loaded {0} parent module'''".format(name.split(u'.')[-1])
    # ModuleType can't accept a unicode type on PY2
    module = types.ModuleType(str(name))
    exec(code, module.__dict__)
    sys.modules[name] = module


def _mod_type(module_path):
    if module_path.startswith(SALT_BASE_PATH):
        return u'int'
    return u'ext'


# TODO: move somewhere else?
class FilterDictWrapper(MutableMapping):
    '''
    Create a dict which wraps another dict with a specific key suffix on get

    This is to replace "filter_load"
    '''
    def __init__(self, d, suffix):
        self._dict = d
        self.suffix = suffix

    def __setitem__(self, key, val):
        self._dict[key] = val

    def __delitem__(self, key):
        del self._dict[key]

    def __getitem__(self, key):
        return self._dict[key + self.suffix]

    def __len__(self):
        return len(self._dict)

    def __iter__(self):
        for key in self._dict:
            if key.endswith(self.suffix):
                yield key.replace(self.suffix, u'')


class LazyLoader(salt.utils.lazy.LazyDict):
    '''
    A pseduo-dictionary which has a set of keys which are the
    name of the module and function, delimited by a dot. When
    the value of the key is accessed, the function is then loaded
    from disk and into memory.

    .. note::

        Iterating over keys will cause all modules to be loaded.

    :param list module_dirs: A list of directories on disk to search for modules
    :param opts dict: The salt options dictionary.
    :param tag str': The tag for the type of module to load
    :param func mod_type_check: A function which can be used to verify files
    :param dict pack: A dictionary of function to be packed into modules as they are loaded
    :param list whitelist: A list of modules to whitelist
    :param bool virtual_enable: Whether or not to respect the __virtual__ function when loading modules.
    :param str virtual_funcs: The name of additional functions in the module to call to verify its functionality.
                                If not true, the module will not load.
    :returns: A LazyLoader object which functions as a dictionary. Keys are 'module.function' and values
    are function references themselves which are loaded on-demand.
    # TODO:
        - move modules_max_memory into here
        - singletons (per tag)
    '''

    mod_dict_class = salt.utils.odict.OrderedDict

    def __init__(self,
                 module_dirs,
                 opts=None,
                 tag=u'module',
                 loaded_base_name=None,
                 mod_type_check=None,
                 pack=None,
                 whitelist=None,
                 virtual_enable=True,
                 static_modules=None,
                 proxy=None,
                 virtual_funcs=None,
                 ):  # pylint: disable=W0231
        '''
        In pack, if any of the values are None they will be replaced with an
        empty context-specific dict
        '''

        self.inject_globals = {}
        self.pack = {} if pack is None else pack
        if opts is None:
            opts = {}
        threadsafety = not opts.get(u'multiprocessing')
        self.context_dict = salt.utils.context.ContextDict(threadsafe=threadsafety)
        self.opts = self.__prep_mod_opts(opts)

        self.module_dirs = module_dirs
        self.tag = tag
        self.loaded_base_name = loaded_base_name or LOADED_BASE_NAME
        self.mod_type_check = mod_type_check or _mod_type

        if u'__context__' not in self.pack:
            self.pack[u'__context__'] = None

        for k, v in six.iteritems(self.pack):
            if v is None:  # if the value of a pack is None, lets make an empty dict
                self.context_dict.setdefault(k, {})
                self.pack[k] = salt.utils.context.NamespacedDictWrapper(self.context_dict, k)

        self.whitelist = whitelist
        self.virtual_enable = virtual_enable
        self.initial_load = True

        # names of modules that we don't have (errors, __virtual__, etc.)
        self.missing_modules = {}  # mapping of name -> error
        self.loaded_modules = {}  # mapping of module_name -> dict_of_functions
        self.loaded_files = set()  # TODO: just remove them from file_mapping?
        self.static_modules = static_modules if static_modules else []

        if virtual_funcs is None:
            virtual_funcs = []
        self.virtual_funcs = virtual_funcs

        self.disabled = set(
            self.opts.get(
                u'disable_{0}{1}'.format(
                    self.tag,
                    u'' if self.tag[-1] == u's' else u's'
                ),
                []
            )
        )

        self.refresh_file_mapping()

        super(LazyLoader, self).__init__()  # late init the lazy loader
        # create all of the import namespaces
        _generate_module(u'{0}.int'.format(self.loaded_base_name))
        _generate_module(u'{0}.int.{1}'.format(self.loaded_base_name, tag))
        _generate_module(u'{0}.ext'.format(self.loaded_base_name))
        _generate_module(u'{0}.ext.{1}'.format(self.loaded_base_name, tag))

    def __getitem__(self, item):
        '''
        Override the __getitem__ in order to decorate the returned function if we need
        to last-minute inject globals
        '''
        func = super(LazyLoader, self).__getitem__(item)
        if self.inject_globals:
            return global_injector_decorator(self.inject_globals)(func)
        else:
            return func

    def __getattr__(self, mod_name):
        '''
        Allow for "direct" attribute access-- this allows jinja templates to
        access things like `salt.test.ping()`
        '''
        if mod_name in (u'__getstate__', u'__setstate__'):
            return object.__getattribute__(self, mod_name)

        # if we have an attribute named that, lets return it.
        try:
            return object.__getattr__(self, mod_name)  # pylint: disable=no-member
        except AttributeError:
            pass

        # otherwise we assume its jinja template access
        if mod_name not in self.loaded_modules and not self.loaded:
            for name in self._iter_files(mod_name):
                if name in self.loaded_files:
                    continue
                # if we got what we wanted, we are done
                if self._load_module(name) and mod_name in self.loaded_modules:
                    break
        if mod_name in self.loaded_modules:
            return self.loaded_modules[mod_name]
        else:
            raise AttributeError(mod_name)

    def missing_fun_string(self, function_name):
        '''
        Return the error string for a missing function.

        This can range from "not available' to "__virtual__" returned False
        '''
        mod_name = function_name.split(u'.')[0]
        if mod_name in self.loaded_modules:
            return u'\'{0}\' is not available.'.format(function_name)
        else:
            try:
                reason = self.missing_modules[mod_name]
            except KeyError:
                return u'\'{0}\' is not available.'.format(function_name)
            else:
                if reason is not None:
                    return u'\'{0}\' __virtual__ returned False: {1}'.format(mod_name, reason)
                else:
                    return u'\'{0}\' __virtual__ returned False'.format(mod_name)

    def refresh_file_mapping(self):
        '''
        refresh the mapping of the FS on disk
        '''
        # map of suffix to description for imp
        self.suffix_map = {}
        suffix_order = [u'']  # local list to determine precedence of extensions
                             # Prefer packages (directories) over modules (single files)!
        for (suffix, mode, kind) in SUFFIXES:
            self.suffix_map[suffix] = (suffix, mode, kind)
            suffix_order.append(suffix)

        if self.opts.get(u'cython_enable', True) is True:
            try:
                global pyximport
                pyximport = __import__(u'pyximport')  # pylint: disable=import-error
                pyximport.install()
                # add to suffix_map so file_mapping will pick it up
                self.suffix_map[u'.pyx'] = tuple()
            except ImportError:
                log.info(u'Cython is enabled in the options but not present '
                    u'in the system path. Skipping Cython modules.')
        # Allow for zipimport of modules
        if self.opts.get(u'enable_zip_modules', True) is True:
            self.suffix_map[u'.zip'] = tuple()
        # allow for module dirs
        if USE_IMPORTLIB:
            self.suffix_map[u''] = (u'', u'', MODULE_KIND_PKG_DIRECTORY)
        else:
            self.suffix_map[u''] = (u'', u'', imp.PKG_DIRECTORY)

        # create mapping of filename (without suffix) to (path, suffix)
        # The files are added in order of priority, so order *must* be retained.
        self.file_mapping = salt.utils.odict.OrderedDict()

        for mod_dir in self.module_dirs:
            files = []
            try:
                # Make sure we have a sorted listdir in order to have expectable override results
                files = sorted(os.listdir(mod_dir))
            except OSError:
                continue  # Next mod_dir
            for filename in files:
                try:
                    if filename.startswith(u'_'):
                        # skip private modules
                        # log messages omitted for obviousness
                        continue  # Next filename
                    f_noext, ext = os.path.splitext(filename)
                    # make sure it is a suffix we support
                    if ext not in self.suffix_map:
                        continue  # Next filename
                    if f_noext in self.disabled:
                        log.trace(
                            u'Skipping %s, it is disabled by configuration',
                            filename
                        )
                        continue  # Next filename
                    fpath = os.path.join(mod_dir, filename)
                    # if its a directory, lets allow us to load that
                    if ext == u'':
                        # is there something __init__?
                        subfiles = os.listdir(fpath)
                        for suffix in suffix_order:
                            if u'' == suffix:
                                continue  # Next suffix (__init__ must have a suffix)
                            init_file = u'__init__{0}'.format(suffix)
                            if init_file in subfiles:
                                break
                        else:
                            continue  # Next filename

                    if f_noext in self.file_mapping:
                        curr_ext = self.file_mapping[f_noext][1]
                        #log.debug("****** curr_ext={0} ext={1} suffix_order={2}".format(curr_ext, ext, suffix_order))
                        if u'' in (curr_ext, ext) and curr_ext != ext:
                            log.error(
                                u'Module/package collision: \'%s\' and \'%s\'',
                                fpath,
                                self.file_mapping[f_noext][0]
                            )
                        if not curr_ext or suffix_order.index(ext) >= suffix_order.index(curr_ext):
                            continue  # Next filename

                    # Made it this far - add it
                    self.file_mapping[f_noext] = (fpath, ext)

                except OSError:
                    continue
        for smod in self.static_modules:
            f_noext = smod.split(u'.')[-1]
            self.file_mapping[f_noext] = (smod, u'.o')

    def clear(self):
        '''
        Clear the dict
        '''
        super(LazyLoader, self).clear()  # clear the lazy loader
        self.loaded_files = set()
        self.missing_modules = {}
        self.loaded_modules = {}
        # if we have been loaded before, lets clear the file mapping since
        # we obviously want a re-do
        if hasattr(self, u'opts'):
            self.refresh_file_mapping()
        self.initial_load = False

    def __prep_mod_opts(self, opts):
        '''
        Strip out of the opts any logger instance
        '''
        if u'__grains__' not in self.pack:
            self.context_dict[u'grains'] = opts.get(u'grains', {})
            self.pack[u'__grains__'] = salt.utils.context.NamespacedDictWrapper(self.context_dict, u'grains', override_name=u'grains')

        if u'__pillar__' not in self.pack:
            self.context_dict[u'pillar'] = opts.get(u'pillar', {})
            self.pack[u'__pillar__'] = salt.utils.context.NamespacedDictWrapper(self.context_dict, u'pillar', override_name=u'pillar')

        mod_opts = {}
        for key, val in list(opts.items()):
            if key == u'logger':
                continue
            mod_opts[key] = val
        return mod_opts

    def _iter_files(self, mod_name):
        '''
        Iterate over all file_mapping files in order of closeness to mod_name
        '''
        # do we have an exact match?
        if mod_name in self.file_mapping:
            yield mod_name

        # do we have a partial match?
        for k in self.file_mapping:
            if mod_name in k:
                yield k

        # anyone else? Bueller?
        for k in self.file_mapping:
            if mod_name not in k:
                yield k

    def _reload_submodules(self, mod):
        submodules = (
            getattr(mod, sname) for sname in dir(mod) if
            isinstance(getattr(mod, sname), mod.__class__)
        )

        # reload only custom "sub"modules
        for submodule in submodules:
            # it is a submodule if the name is in a namespace under mod
            if submodule.__name__.startswith(mod.__name__ + u'.'):
                reload_module(submodule)
                self._reload_submodules(submodule)

    def _load_module(self, name):
        mod = None
        fpath, suffix = self.file_mapping[name]
        self.loaded_files.add(name)
        fpath_dirname = os.path.dirname(fpath)
        try:
            sys.path.append(fpath_dirname)
            if suffix == u'.pyx':
                mod = pyximport.load_module(name, fpath, tempfile.gettempdir())
            elif suffix == u'.o':
                top_mod = __import__(fpath, globals(), locals(), [])
                comps = fpath.split(u'.')
                if len(comps) < 2:
                    mod = top_mod
                else:
                    mod = top_mod
                    for subname in comps[1:]:
                        mod = getattr(mod, subname)
            elif suffix == u'.zip':
                mod = zipimporter(fpath).load_module(name)
            else:
                desc = self.suffix_map[suffix]
                # if it is a directory, we don't open a file
                try:
                    mod_namespace = u'.'.join((
                        self.loaded_base_name,
                        self.mod_type_check(fpath),
                        self.tag,
                        name))
                except TypeError:
                    mod_namespace = u'{0}.{1}.{2}.{3}'.format(
                        self.loaded_base_name,
                        self.mod_type_check(fpath),
                        self.tag,
                        name)
                if suffix == u'':
                    if USE_IMPORTLIB:
                        # pylint: disable=no-member
                        # Package directory, look for __init__
                        loader_details = [
                            (importlib.machinery.SourceFileLoader, importlib.machinery.SOURCE_SUFFIXES),
                            (importlib.machinery.SourcelessFileLoader, importlib.machinery.BYTECODE_SUFFIXES),
                            (importlib.machinery.ExtensionFileLoader, importlib.machinery.EXTENSION_SUFFIXES),
                        ]
                        file_finder = importlib.machinery.FileFinder(
                            fpath_dirname,
                            *loader_details
                        )
                        spec = file_finder.find_spec(mod_namespace)
                        if spec is None:
                            raise ImportError()
                        # TODO: Get rid of load_module in favor of
                        # exec_module below. load_module is deprecated, but
                        # loading using exec_module has been causing odd things
                        # with the magic dunders we pack into the loaded
                        # modules, most notably with salt-ssh's __opts__.
                        mod = spec.loader.load_module()
                        # mod = importlib.util.module_from_spec(spec)
                        # spec.loader.exec_module(mod)
                        # pylint: enable=no-member
                        sys.modules[mod_namespace] = mod
                    else:
                        mod = imp.load_module(mod_namespace, None, fpath, desc)
                    # reload all submodules if necessary
                    if not self.initial_load:
                        self._reload_submodules(mod)
                else:
                    if USE_IMPORTLIB:
                        # pylint: disable=no-member
                        loader = MODULE_KIND_MAP[desc[2]](mod_namespace, fpath)
                        spec = importlib.util.spec_from_file_location(
                            mod_namespace, fpath, loader=loader
                        )
                        if spec is None:
                            raise ImportError()
                        # TODO: Get rid of load_module in favor of
                        # exec_module below. load_module is deprecated, but
                        # loading using exec_module has been causing odd things
                        # with the magic dunders we pack into the loaded
                        # modules, most notably with salt-ssh's __opts__.
                        mod = spec.loader.load_module()
                        #mod = importlib.util.module_from_spec(spec)
                        #spec.loader.exec_module(mod)
                        # pylint: enable=no-member
                        sys.modules[mod_namespace] = mod
                    else:
                        with salt.utils.files.fopen(fpath, desc[1]) as fn_:
                            mod = imp.load_module(mod_namespace, fn_, fpath, desc)
        except IOError:
            raise
        except ImportError as exc:
            if u'magic number' in str(exc):
                error_msg = u'Failed to import {0} {1}. Bad magic number. If migrating from Python2 to Python3, remove all .pyc files and try again.'.format(self.tag, name)
                log.warning(error_msg)
                self.missing_modules[name] = error_msg
            log.debug(
                u'Failed to import %s %s:\n',
                self.tag, name, exc_info=True
            )
            self.missing_modules[name] = exc
            return False
        except Exception as error:
            log.error(
                u'Failed to import %s %s, this is due most likely to a '
                u'syntax error:\n', self.tag, name, exc_info=True
            )
            self.missing_modules[name] = error
            return False
        except SystemExit as error:
            log.error(
                u'Failed to import %s %s as the module called exit()\n',
                self.tag, name, exc_info=True
            )
            self.missing_modules[name] = error
            return False
        finally:
            sys.path.remove(fpath_dirname)

        if hasattr(mod, u'__opts__'):
            mod.__opts__.update(self.opts)
        else:
            mod.__opts__ = self.opts

        # pack whatever other globals we were asked to
        for p_name, p_value in six.iteritems(self.pack):
            setattr(mod, p_name, p_value)

        module_name = mod.__name__.rsplit(u'.', 1)[-1]

        # Call a module's initialization method if it exists
        module_init = getattr(mod, u'__init__', None)
        if inspect.isfunction(module_init):
            try:
                module_init(self.opts)
            except TypeError as e:
                log.error(e)
            except Exception:
                err_string = u'__init__ failed'
                log.debug(
                    u'Error loading %s.%s: %s',
                    self.tag, module_name, err_string, exc_info=True
                )
                self.missing_modules[module_name] = err_string
                self.missing_modules[name] = err_string
                return False

        # if virtual modules are enabled, we need to look for the
        # __virtual__() function inside that module and run it.
        if self.virtual_enable:
            virtual_funcs_to_process = [u'__virtual__'] + self.virtual_funcs
            for virtual_func in virtual_funcs_to_process:
                virtual_ret, module_name, virtual_err, virtual_aliases = \
                    self.process_virtual(mod, module_name, virtual_func)
                if virtual_err is not None:
                    log.trace(
                        u'Error loading %s.%s: %s',
                        self.tag, module_name, virtual_err
                    )

                # if process_virtual returned a non-True value then we are
                # supposed to not process this module
                if virtual_ret is not True and module_name not in self.missing_modules:
                    # If a module has information about why it could not be loaded, record it
                    self.missing_modules[module_name] = virtual_err
                    self.missing_modules[name] = virtual_err
                    return False
        else:
            virtual_aliases = ()

        # If this is a proxy minion then MOST modules cannot work. Therefore, require that
        # any module that does work with salt-proxy-minion define __proxyenabled__ as a list
        # containing the names of the proxy types that the module supports.
        #
        # Render modules and state modules are OK though
        if u'proxy' in self.opts:
            if self.tag in [u'grains', u'proxy']:
                if not hasattr(mod, u'__proxyenabled__') or \
                        (self.opts[u'proxy'][u'proxytype'] not in mod.__proxyenabled__ and
                            u'*' not in mod.__proxyenabled__):
                    err_string = u'not a proxy_minion enabled module'
                    self.missing_modules[module_name] = err_string
                    self.missing_modules[name] = err_string
                    return False

        if getattr(mod, u'__load__', False) is not False:
            log.info(
                u'The functions from module \'%s\' are being loaded from the '
                u'provided __load__ attribute', module_name
            )

        # If we had another module by the same virtual name, we should put any
        # new functions under the existing dictionary.
        mod_names = [module_name] + list(virtual_aliases)
        mod_dict = dict((
            (x, self.loaded_modules.get(x, self.mod_dict_class()))
            for x in mod_names
        ))

        for attr in getattr(mod, u'__load__', dir(mod)):
            if attr.startswith(u'_'):
                # private functions are skipped
                continue
            func = getattr(mod, attr)
            if not inspect.isfunction(func) and not isinstance(func, functools.partial):
                # Not a function!? Skip it!!!
                continue
            # Let's get the function name.
            # If the module has the __func_alias__ attribute, it must be a
            # dictionary mapping in the form of(key -> value):
            #   <real-func-name> -> <desired-func-name>
            #
            # It default's of course to the found callable attribute name
            # if no alias is defined.
            funcname = getattr(mod, u'__func_alias__', {}).get(attr, attr)
            for tgt_mod in mod_names:
                try:
                    full_funcname = u'.'.join((tgt_mod, funcname))
                except TypeError:
                    full_funcname = u'{0}.{1}'.format(tgt_mod, funcname)
                # Save many references for lookups
                # Careful not to overwrite existing (higher priority) functions
                if full_funcname not in self._dict:
                    self._dict[full_funcname] = func
                if funcname not in mod_dict[tgt_mod]:
                    setattr(mod_dict[tgt_mod], funcname, func)
                    mod_dict[tgt_mod][funcname] = func
                    self._apply_outputter(func, mod)

        # enforce depends
        try:
            Depends.enforce_dependencies(self._dict, self.tag)
        except RuntimeError as exc:
            log.info(
                u'Depends.enforce_dependencies() failed for the following '
                u'reason: %s', exc
            )

        for tgt_mod in mod_names:
            self.loaded_modules[tgt_mod] = mod_dict[tgt_mod]
        return True

    def _load(self, key):
        '''
        Load a single item if you have it
        '''
        # if the key doesn't have a '.' then it isn't valid for this mod dict
        if not isinstance(key, six.string_types) or u'.' not in key:
            raise KeyError
        mod_name, _ = key.split(u'.', 1)
        if mod_name in self.missing_modules:
            return True
        # if the modulename isn't in the whitelist, don't bother
        if self.whitelist and mod_name not in self.whitelist:
            raise KeyError

        def _inner_load(mod_name):
            for name in self._iter_files(mod_name):
                if name in self.loaded_files:
                    continue
                # if we got what we wanted, we are done
                if self._load_module(name) and key in self._dict:
                    return True
            return False

        # try to load the module
        ret = None
        reloaded = False
        # re-scan up to once, IOErrors or a failed load cause re-scans of the
        # filesystem
        while True:
            try:
                ret = _inner_load(mod_name)
                if not reloaded and ret is not True:
                    self.refresh_file_mapping()
                    reloaded = True
                    continue
                break
            except IOError:
                if not reloaded:
                    self.refresh_file_mapping()
                    reloaded = True
                continue

        return ret

    def _load_all(self):
        '''
        Load all of them
        '''
        for name in self.file_mapping:
            if name in self.loaded_files or name in self.missing_modules:
                continue
            self._load_module(name)

        self.loaded = True

    def reload_modules(self):
        self.loaded_files = set()
        self._load_all()

    def _apply_outputter(self, func, mod):
        '''
        Apply the __outputter__ variable to the functions
        '''
        if hasattr(mod, u'__outputter__'):
            outp = mod.__outputter__
            if func.__name__ in outp:
                func.__outputter__ = outp[func.__name__]

    def process_virtual(self, mod, module_name, virtual_func=u'__virtual__'):
        '''
        Given a loaded module and its default name determine its virtual name

        This function returns a tuple. The first value will be either True or
        False and will indicate if the module should be loaded or not (i.e. if
        it threw and exception while processing its __virtual__ function). The
        second value is the determined virtual name, which may be the same as
        the value provided.

        The default name can be calculated as follows::

            module_name = mod.__name__.rsplit('.', 1)[-1]
        '''

        # The __virtual__ function will return either a True or False value.
        # If it returns a True value it can also set a module level attribute
        # named __virtualname__ with the name that the module should be
        # referred to as.
        #
        # This allows us to have things like the pkg module working on all
        # platforms under the name 'pkg'. It also allows for modules like
        # augeas_cfg to be referred to as 'augeas', which would otherwise have
        # namespace collisions. And finally it allows modules to return False
        # if they are not intended to run on the given platform or are missing
        # dependencies.
        virtual_aliases = getattr(mod, u'__virtual_aliases__', tuple())
        try:
            error_reason = None
            if hasattr(mod, u'__virtual__') and inspect.isfunction(mod.__virtual__):
                try:
                    start = time.time()
                    virtual = getattr(mod, virtual_func)()
                    if isinstance(virtual, tuple):
                        error_reason = virtual[1]
                        virtual = virtual[0]
                    if self.opts.get(u'virtual_timer', False):
                        end = time.time() - start
                        msg = u'Virtual function took {0} seconds for {1}'.format(
                                end, module_name)
                        log.warning(msg)
                except Exception as exc:
                    error_reason = (
                        u'Exception raised when processing __virtual__ function'
                        u' for {0}. Module will not be loaded: {1}'.format(
                            mod.__name__, exc))
                    log.error(error_reason, exc_info_on_loglevel=logging.DEBUG)
                    virtual = None
                # Get the module's virtual name
                virtualname = getattr(mod, u'__virtualname__', virtual)
                if not virtual:
                    # if __virtual__() evaluates to False then the module
                    # wasn't meant for this platform or it's not supposed to
                    # load for some other reason.

                    # Some modules might accidentally return None and are
                    # improperly loaded
                    if virtual is None:
                        log.warning(
                            u'%s.__virtual__() is wrongly returning `None`. '
                            u'It should either return `True`, `False` or a new '
                            u'name. If you\'re the developer of the module '
                            u'\'%s\', please fix this.', mod.__name__, module_name
                        )

                    return (False, module_name, error_reason, virtual_aliases)

                # At this point, __virtual__ did not return a
                # boolean value, let's check for deprecated usage
                # or module renames
                if virtual is not True and module_name != virtual:
                    # The module is renaming itself. Updating the module name
                    # with the new name
                    log.trace(u'Loaded %s as virtual %s', module_name, virtual)

                    if not hasattr(mod, u'__virtualname__'):
                        salt.utils.versions.warn_until(
                            u'Hydrogen',
                            u'The \'{0}\' module is renaming itself in its '
                            u'__virtual__() function ({1} => {2}). Please '
                            u'set it\'s virtual name as the '
                            u'\'__virtualname__\' module attribute. '
                            u'Example: "__virtualname__ = \'{2}\'"'.format(
                                mod.__name__,
                                module_name,
                                virtual
                            )
                        )

                    if virtualname != virtual:
                        # The __virtualname__ attribute does not match what's
                        # being returned by the __virtual__() function. This
                        # should be considered an error.
                        log.error(
                            u'The module \'%s\' is showing some bad usage. Its '
                            u'__virtualname__ attribute is set to \'%s\' yet the '
                            u'__virtual__() function is returning \'%s\'. These '
                            u'values should match!',
                            mod.__name__, virtualname, virtual
                        )

                    module_name = virtualname

                # If the __virtual__ function returns True and __virtualname__
                # is set then use it
                elif virtual is True and virtualname != module_name:
                    if virtualname is not True:
                        module_name = virtualname

        except KeyError:
            # Key errors come out of the virtual function when passing
            # in incomplete grains sets, these can be safely ignored
            # and logged to debug, still, it includes the traceback to
            # help debugging.
            log.debug(u'KeyError when loading %s', module_name, exc_info=True)

        except Exception:
            # If the module throws an exception during __virtual__()
            # then log the information and continue to the next.
            log.error(
                u'Failed to read the virtual function for %s: %s',
                self.tag, module_name, exc_info=True
            )
            return (False, module_name, error_reason, virtual_aliases)

        return (True, module_name, None, virtual_aliases)


def global_injector_decorator(inject_globals):
    '''
    Decorator used by the LazyLoader to inject globals into a function at
    execute time.

    globals
        Dictionary with global variables to inject
    '''
    def inner_decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            with salt.utils.context.func_globals_inject(f, **inject_globals):
                return f(*args, **kwargs)
        return wrapper
    return inner_decorator
