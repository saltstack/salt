"""
The Salt loader is the core to Salt's plugin system, the loader scans
directories for python loadable code and organizes the code into the
plugin interfaces used by Salt.
"""

import contextlib
import logging
import os
import re
import time
import types

import salt.config
import salt.defaults.events
import salt.defaults.exitcodes
import salt.loader.context
import salt.syspaths
import salt.utils.args
import salt.utils.context
import salt.utils.data
import salt.utils.dictupdate
import salt.utils.event
import salt.utils.files
import salt.utils.lazy
import salt.utils.odict
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.versions
from salt.exceptions import LoaderError
from salt.template import check_render_pipe_str
from salt.utils import entrypoints

from .lazy import SALT_BASE_PATH, FilterDictWrapper, LazyLoader

log = logging.getLogger(__name__)

# Because on the cloud drivers we do `from salt.cloud.libcloudfuncs import *`
# which simplifies code readability, it adds some unsupported functions into
# the driver's module scope.
# We list un-supported functions here. These will be removed from the loaded.
#  TODO:  remove the need for this cross-module code. Maybe use NotImplemented
LIBCLOUD_FUNCS_NOT_SUPPORTED = (
    "parallels.avail_sizes",
    "parallels.avail_locations",
    "proxmox.avail_sizes",
)

SALT_INTERNAL_LOADERS_PATHS = (
    str(SALT_BASE_PATH / "auth"),
    str(SALT_BASE_PATH / "beacons"),
    str(SALT_BASE_PATH / "cache"),
    str(SALT_BASE_PATH / "client" / "ssh" / "wrapper"),
    str(SALT_BASE_PATH / "cloud" / "clouds"),
    str(SALT_BASE_PATH / "engines"),
    str(SALT_BASE_PATH / "executors"),
    str(SALT_BASE_PATH / "fileserver"),
    str(SALT_BASE_PATH / "grains"),
    str(SALT_BASE_PATH / "log" / "handlers"),
    str(SALT_BASE_PATH / "matchers"),
    str(SALT_BASE_PATH / "metaproxy"),
    str(SALT_BASE_PATH / "modules"),
    str(SALT_BASE_PATH / "netapi"),
    str(SALT_BASE_PATH / "output"),
    str(SALT_BASE_PATH / "pillar"),
    str(SALT_BASE_PATH / "proxy"),
    str(SALT_BASE_PATH / "queues"),
    str(SALT_BASE_PATH / "renderers"),
    str(SALT_BASE_PATH / "returners"),
    str(SALT_BASE_PATH / "roster"),
    str(SALT_BASE_PATH / "runners"),
    str(SALT_BASE_PATH / "sdb"),
    str(SALT_BASE_PATH / "serializers"),
    str(SALT_BASE_PATH / "spm" / "pkgdb"),
    str(SALT_BASE_PATH / "spm" / "pkgfiles"),
    str(SALT_BASE_PATH / "states"),
    str(SALT_BASE_PATH / "thorium"),
    str(SALT_BASE_PATH / "tokens"),
    str(SALT_BASE_PATH / "tops"),
    str(SALT_BASE_PATH / "utils"),
    str(SALT_BASE_PATH / "wheel"),
)


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
    load_extensions=True,
):
    if tag is None:
        tag = ext_type
    sys_types = os.path.join(base_path or str(SALT_BASE_PATH), int_type or ext_type)
    ext_types = os.path.join(opts["extension_modules"], ext_type)

    if not sys_types.startswith(SALT_INTERNAL_LOADERS_PATHS):
        raise RuntimeError(
            "{!r} is not considered a salt internal loader path. If this "
            "is a new loader being added, please also add it to "
            "{}.SALT_INTERNAL_LOADERS_PATHS.".format(sys_types, __name__)
        )

    ext_type_types = []
    if ext_dirs:
        if ext_type_dirs is None:
            ext_type_dirs = "{}_dirs".format(tag)
        if ext_type_dirs in opts:
            ext_type_types.extend(opts[ext_type_dirs])
        if ext_type_dirs and load_extensions is True:
            for entry_point in entrypoints.iter_entry_points("salt.loader"):
                with catch_entry_points_exception(entry_point) as ctx:
                    loaded_entry_point = entry_point.load()
                if ctx.exception_caught:
                    continue

                # Old way of defining loader entry points
                #   [options.entry_points]
                #   salt.loader=
                #     runner_dirs = thirpartypackage.loader:func_to_get_list_of_dirs
                #     module_dirs = thirpartypackage.loader:func_to_get_list_of_dirs
                #
                #
                # New way of defining entrypoints
                #   [options.entry_points]
                #   salt.loader=
                #     <this-name-does-not-matter> = thirpartypackage
                #     <this-name-does-not-matter> = thirpartypackage:callable
                #
                # We try and see if the thirpartypackage has a `ext_type` sub module, and if so,
                # we append it to loaded_entry_point_paths.
                # If the entry-point is in the form of `thirpartypackage:callable`, the return of that
                # callable must be a dictionary where the keys are the `ext_type`'s and the values must be
                # lists of paths.

                # We could feed the paths we load directly to `ext_type_types`, but we would not
                # check for duplicates
                loaded_entry_point_paths = set()

                if isinstance(loaded_entry_point, types.FunctionType):
                    # If the entry point object is a function, we have two scenarios
                    #   1: It returns a list; This is an old style entry entry_point
                    #   2: It returns a dictionary; This is a new style entry point
                    with catch_entry_points_exception(entry_point) as ctx:
                        loaded_entry_point_value = loaded_entry_point()
                    if ctx.exception_caught:
                        continue

                    if isinstance(loaded_entry_point_value, dict):
                        # This is new style entry-point and it returns a dictionary.
                        # It MUST contain `ext_type` in it's keys to be considered
                        if ext_type not in loaded_entry_point_value:
                            continue
                        with catch_entry_points_exception(entry_point) as ctx:
                            if isinstance(loaded_entry_point_value[ext_type], str):
                                # No strings please!
                                raise ValueError(
                                    "The callable must return an iterable of strings. "
                                    "A single string is not supported."
                                )
                            for path in loaded_entry_point_value[ext_type]:
                                loaded_entry_point_paths.add(path)
                    else:
                        # This is old style entry-point, and, as such, the entry point name MUST
                        # match the value of `ext_type_dirs
                        if entry_point.name != ext_type_dirs:
                            continue
                        for path in loaded_entry_point_value:
                            loaded_entry_point_paths.add(path)
                elif isinstance(loaded_entry_point, types.ModuleType):
                    # This is a new style entry points definition which just points us to a package
                    #
                    # We try and see if the thirpartypackage has a `ext_type` sub module, and if so,
                    # we append it to loaded_entry_point_paths.
                    for loaded_entry_point_path in loaded_entry_point.__path__:
                        with catch_entry_points_exception(entry_point) as ctx:
                            entry_point_ext_type_package_path = os.path.join(
                                loaded_entry_point_path, ext_type
                            )
                            if not os.path.exists(entry_point_ext_type_package_path):
                                continue
                        if ctx.exception_caught:
                            continue
                        loaded_entry_point_paths.add(entry_point_ext_type_package_path)
                else:
                    with catch_entry_points_exception(entry_point):
                        raise ValueError(
                            "Don't know how to load a salt extension from {}".format(
                                loaded_entry_point
                            )
                        )

                # Finally, we check all paths that we collected to see if they exist
                for path in loaded_entry_point_paths:
                    if os.path.exists(path):
                        ext_type_types.append(path)

    cli_module_dirs = []
    # The dirs can be any module dir, or a in-tree _{ext_type} dir
    for _dir in opts.get("module_dirs", []):
        # Prepend to the list to match cli argument ordering
        maybe_dir = os.path.join(_dir, ext_type)
        if os.path.isdir(maybe_dir):
            cli_module_dirs.insert(0, maybe_dir)
            continue

        maybe_dir = os.path.join(_dir, "_{}".format(ext_type))
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
    proxy=None,
):
    """
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
    """
    # TODO Publish documentation for module whitelisting
    if not whitelist:
        whitelist = opts.get("whitelist_modules", None)
    ret = LazyLoader(
        _module_dirs(opts, "modules", "module"),
        opts,
        tag="module",
        pack={"__context__": context, "__utils__": utils, "__proxy__": proxy},
        whitelist=whitelist,
        loaded_base_name=loaded_base_name,
        static_modules=static_modules,
        extra_module_dirs=utils.module_dirs if utils else None,
        pack_self="__salt__",
    )

    # Load any provider overrides from the configuration file providers option
    #  Note: Providers can be pkg, service, user or group - not to be confused
    #        with cloud providers.
    providers = opts.get("providers", False)
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
                        f_key = "{}{}".format(mod, func[func.rindex(".") :])
                        ret[f_key] = funcs[func]

    if notify:
        with salt.utils.event.get_event("minion", opts=opts, listen=False) as evt:
            evt.fire_event(
                {"complete": True}, tag=salt.defaults.events.MINION_MOD_REFRESH_COMPLETE
            )

    return ret


def raw_mod(opts, name, functions, mod="modules"):
    """
    Returns a single module loaded raw and bypassing the __virtual__ function

    .. code-block:: python

        import salt.config
        import salt.loader

        __opts__ = salt.config.minion_config('/etc/salt/minion')
        testmod = salt.loader.raw_mod(__opts__, 'test', None)
        testmod['test.ping']()
    """
    loader = LazyLoader(
        _module_dirs(opts, mod, "module"),
        opts,
        tag="rawmodule",
        virtual_enable=False,
        pack={"__salt__": functions},
    )
    # if we don't have the module, return an empty dict
    if name not in loader.file_mapping:
        return {}

    # load a single module (the one passed in)
    loader._load_module(name)
    # return a copy of *just* the funcs for `name`
    return dict({x: loader[x] for x in loader._dict})


def metaproxy(opts, loaded_base_name=None):
    """
    Return functions used in the meta proxy
    """
    return LazyLoader(
        _module_dirs(opts, "metaproxy"),
        opts,
        tag="metaproxy",
        loaded_base_name=loaded_base_name,
    )


def matchers(opts):
    """
    Return the matcher services plugins
    """
    return LazyLoader(_module_dirs(opts, "matchers"), opts, tag="matchers")


def engines(opts, functions, runners, utils, proxy=None):
    """
    Return the master services plugins
    """
    pack = {
        "__salt__": functions,
        "__runners__": runners,
        "__proxy__": proxy,
        "__utils__": utils,
    }
    return LazyLoader(
        _module_dirs(opts, "engines"),
        opts,
        tag="engines",
        pack=pack,
        extra_module_dirs=utils.module_dirs if utils else None,
    )


def proxy(
    opts,
    functions=None,
    returners=None,
    whitelist=None,
    utils=None,
    context=None,
    pack_self="__proxy__",
):
    """
    Returns the proxy module for this salt-proxy-minion
    """
    return LazyLoader(
        _module_dirs(opts, "proxy"),
        opts,
        tag="proxy",
        pack={
            "__salt__": functions,
            "__ret__": returners,
            "__utils__": utils,
            "__context__": context,
        },
        extra_module_dirs=utils.module_dirs if utils else None,
        pack_self=pack_self,
    )


def returners(opts, functions, whitelist=None, context=None, proxy=None):
    """
    Returns the returner modules
    """
    return LazyLoader(
        _module_dirs(opts, "returners", "returner"),
        opts,
        tag="returner",
        whitelist=whitelist,
        pack={"__salt__": functions, "__context__": context, "__proxy__": proxy or {}},
    )


def utils(opts, whitelist=None, context=None, proxy=None, pack_self=None):
    """
    Returns the utility modules
    """
    return LazyLoader(
        _module_dirs(opts, "utils", ext_type_dirs="utils_dirs", load_extensions=False),
        opts,
        tag="utils",
        whitelist=whitelist,
        pack={"__context__": context, "__proxy__": proxy or {}},
        pack_self=pack_self,
    )


def pillars(opts, functions, context=None):
    """
    Returns the pillars modules
    """
    _utils = utils(opts)
    ret = LazyLoader(
        _module_dirs(opts, "pillar"),
        opts,
        tag="pillar",
        pack={"__salt__": functions, "__context__": context, "__utils__": _utils},
        extra_module_dirs=_utils.module_dirs,
        pack_self="__ext_pillar__",
    )
    return FilterDictWrapper(ret, ".ext_pillar")


def tops(opts):
    """
    Returns the tops modules
    """
    if "master_tops" not in opts:
        return {}
    whitelist = list(opts["master_tops"].keys())
    ret = LazyLoader(
        _module_dirs(opts, "tops", "top"),
        opts,
        tag="top",
        whitelist=whitelist,
    )
    return FilterDictWrapper(ret, ".top")


def wheels(opts, whitelist=None, context=None):
    """
    Returns the wheels modules
    """
    if context is None:
        context = {}
    return LazyLoader(
        _module_dirs(opts, "wheel"),
        opts,
        tag="wheel",
        whitelist=whitelist,
        pack={"__context__": context},
    )


def outputters(opts):
    """
    Returns the outputters modules

    :param dict opts: The Salt options dictionary
    :returns: LazyLoader instance, with only outputters present in the keyspace
    """
    ret = LazyLoader(
        _module_dirs(opts, "output", ext_type_dirs="outputter_dirs"),
        opts,
        tag="output",
    )
    wrapped_ret = FilterDictWrapper(ret, ".output")
    # TODO: this name seems terrible... __salt__ should always be execution mods
    ret.pack["__salt__"] = wrapped_ret
    return wrapped_ret


def serializers(opts):
    """
    Returns the serializers modules
    :param dict opts: The Salt options dictionary
    :returns: LazyLoader instance, with only serializers present in the keyspace
    """
    return LazyLoader(
        _module_dirs(opts, "serializers"),
        opts,
        tag="serializers",
    )


def eauth_tokens(opts):
    """
    Returns the tokens modules
    :param dict opts: The Salt options dictionary
    :returns: LazyLoader instance, with only token backends present in the keyspace
    """
    return LazyLoader(
        _module_dirs(opts, "tokens"),
        opts,
        tag="tokens",
    )


def auth(opts, whitelist=None):
    """
    Returns the auth modules

    :param dict opts: The Salt options dictionary
    :returns: LazyLoader
    """
    return LazyLoader(
        _module_dirs(opts, "auth"),
        opts,
        tag="auth",
        whitelist=whitelist,
        pack={"__salt__": minion_mods(opts)},
    )


def fileserver(opts, backends):
    """
    Returns the file server modules
    """
    _utils = utils(opts)

    if backends is not None:
        if not isinstance(backends, list):
            backends = [backends]

        # If backend is a VCS, add both the '-fs' and non '-fs' versions to the list.
        # Use a set to keep them unique
        backend_set = set()
        vcs_re = re.compile("^(git|svn|hg)(?:fs)?$")
        for backend in backends:
            match = vcs_re.match(backend)
            if match:
                backend_set.add(match.group(1))
                backend_set.add(match.group(1) + "fs")
            else:
                backend_set.add(backend)
        backends = list(backend_set)

    return LazyLoader(
        _module_dirs(opts, "fileserver"),
        opts,
        tag="fileserver",
        whitelist=backends,
        pack={"__utils__": _utils},
        extra_module_dirs=_utils.module_dirs,
    )


def roster(opts, runner=None, utils=None, whitelist=None):
    """
    Returns the roster modules
    """
    return LazyLoader(
        _module_dirs(opts, "roster"),
        opts,
        tag="roster",
        whitelist=whitelist,
        pack={"__runner__": runner, "__utils__": utils},
        extra_module_dirs=utils.module_dirs if utils else None,
    )


def thorium(opts, functions, runners):
    """
    Load the thorium runtime modules
    """
    pack = {"__salt__": functions, "__runner__": runners, "__context__": {}}
    ret = LazyLoader(_module_dirs(opts, "thorium"), opts, tag="thorium", pack=pack)
    ret.pack["__thorium__"] = ret
    return ret


def states(
    opts, functions, utils, serializers, whitelist=None, proxy=None, context=None
):
    """
    Returns the state modules

    :param dict opts: The Salt options dictionary
    :param dict functions: A dictionary of minion modules, with module names as
                            keys and funcs as values.

    .. code-block:: python

        import salt.config
        import salt.loader

        __opts__ = salt.config.minion_config('/etc/salt/minion')
        statemods = salt.loader.states(__opts__, None, None)
    """
    if context is None:
        context = {}

    return LazyLoader(
        _module_dirs(opts, "states"),
        opts,
        tag="states",
        pack={
            "__salt__": functions,
            "__proxy__": proxy or {},
            "__utils__": utils,
            "__serializers__": serializers,
            "__context__": context,
        },
        whitelist=whitelist,
        extra_module_dirs=utils.module_dirs if utils else None,
        pack_self="__states__",
    )


def beacons(opts, functions, context=None, proxy=None):
    """
    Load the beacon modules

    :param dict opts: The Salt options dictionary
    :param dict functions: A dictionary of minion modules, with module names as
                            keys and funcs as values.
    """
    return LazyLoader(
        _module_dirs(opts, "beacons"),
        opts,
        tag="beacons",
        pack={"__context__": context, "__salt__": functions, "__proxy__": proxy or {}},
        virtual_funcs=[],
    )


def log_handlers(opts):
    """
    Returns the custom logging handler modules

    :param dict opts: The Salt options dictionary
    """
    ret = LazyLoader(
        _module_dirs(
            opts,
            "log_handlers",
            int_type="handlers",
            base_path=str(SALT_BASE_PATH / "log"),
        ),
        opts,
        tag="log_handlers",
    )
    return FilterDictWrapper(ret, ".setup_handlers")


def ssh_wrapper(opts, functions=None, context=None):
    """
    Returns the custom logging handler modules
    """
    return LazyLoader(
        _module_dirs(
            opts,
            "wrapper",
            base_path=str(SALT_BASE_PATH / "client" / "ssh"),
        ),
        opts,
        tag="wrapper",
        pack={"__salt__": functions, "__context__": context},
    )


def render(opts, functions, states=None, proxy=None, context=None):
    """
    Returns the render modules
    """
    if context is None:
        context = {}

    pack = {
        "__salt__": functions,
        "__grains__": opts.get("grains", {}),
        "__context__": context,
    }

    if states:
        pack["__states__"] = states

    if proxy is None:
        proxy = {}
    pack["__proxy__"] = proxy

    ret = LazyLoader(
        _module_dirs(
            opts,
            "renderers",
            "render",
            ext_type_dirs="render_dirs",
        ),
        opts,
        tag="render",
        pack=pack,
    )
    rend = FilterDictWrapper(ret, ".render")

    if not check_render_pipe_str(
        opts["renderer"], rend, opts["renderer_blacklist"], opts["renderer_whitelist"]
    ):
        err = (
            "The renderer {} is unavailable, this error is often because "
            "the needed software is unavailable".format(opts["renderer"])
        )
        log.critical(err)
        raise LoaderError(err)
    return rend


def grain_funcs(opts, proxy=None, context=None):
    """
    Returns the grain functions

      .. code-block:: python

          import salt.config
          import salt.loader

          __opts__ = salt.config.minion_config('/etc/salt/minion')
          grainfuncs = salt.loader.grain_funcs(__opts__)
    """
    _utils = utils(opts, proxy=proxy)
    pack = {"__utils__": utils(opts, proxy=proxy), "__context__": context}
    ret = LazyLoader(
        _module_dirs(
            opts,
            "grains",
            "grain",
            ext_type_dirs="grains_dirs",
        ),
        opts,
        tag="grains",
        extra_module_dirs=_utils.module_dirs,
        pack=pack,
    )
    ret.pack["__utils__"] = _utils
    return ret


def _format_cached_grains(cached_grains):
    """
    Returns cached grains with fixed types, like tuples.
    """
    if cached_grains.get("osrelease_info"):
        osrelease_info = cached_grains["osrelease_info"]
        if isinstance(osrelease_info, list):
            cached_grains["osrelease_info"] = tuple(osrelease_info)
    return cached_grains


def _load_cached_grains(opts, cfn):
    """
    Returns the grains cached in cfn, or None if the cache is too old or is
    corrupted.
    """
    if not os.path.isfile(cfn):
        log.debug("Grains cache file does not exist.")
        return None

    grains_cache_age = int(time.time() - os.path.getmtime(cfn))
    if grains_cache_age > opts.get("grains_cache_expiration", 300):
        log.debug(
            "Grains cache last modified %s seconds ago and cache "
            "expiration is set to %s. Grains cache expired. "
            "Refreshing.",
            grains_cache_age,
            opts.get("grains_cache_expiration", 300),
        )
        return None

    if opts.get("refresh_grains_cache", False):
        log.debug("refresh_grains_cache requested, Refreshing.")
        return None

    log.debug("Retrieving grains from cache")
    try:
        with salt.utils.files.fopen(cfn, "rb") as fp_:
            cached_grains = salt.utils.data.decode(
                salt.payload.load(fp_), preserve_tuples=True
            )
        if not cached_grains:
            log.debug("Cached grains are empty, cache might be corrupted. Refreshing.")
            return None

        return _format_cached_grains(cached_grains)
    except OSError:
        return None


def grains(opts, force_refresh=False, proxy=None, context=None):
    """
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
    """
    # Need to re-import salt.config, somehow it got lost when a minion is starting
    import salt.config

    # if we have no grains, lets try loading from disk (TODO: move to decorator?)
    cfn = os.path.join(opts["cachedir"], "grains.cache.p")
    if not force_refresh and opts.get("grains_cache", False):
        cached_grains = _load_cached_grains(opts, cfn)
        if cached_grains:
            return cached_grains
    else:
        log.debug("Grains refresh requested. Refreshing grains.")

    if opts.get("skip_grains", False):
        return {}
    grains_deep_merge = opts.get("grains_deep_merge", False) is True
    if "conf_file" in opts:
        pre_opts = {}
        pre_opts.update(
            salt.config.load_config(
                opts["conf_file"],
                "SALT_MINION_CONFIG",
                salt.config.DEFAULT_MINION_OPTS["conf_file"],
            )
        )
        default_include = pre_opts.get("default_include", opts["default_include"])
        include = pre_opts.get("include", [])
        pre_opts.update(
            salt.config.include_config(
                default_include, opts["conf_file"], verbose=False
            )
        )
        pre_opts.update(
            salt.config.include_config(include, opts["conf_file"], verbose=True)
        )
        if "grains" in pre_opts:
            opts["grains"] = pre_opts["grains"]
        else:
            opts["grains"] = {}
    else:
        opts["grains"] = {}

    grains_data = {}
    blist = opts.get("grains_blacklist", [])
    funcs = grain_funcs(opts, proxy=proxy, context=context or {})
    if force_refresh:  # if we refresh, lets reload grain modules
        funcs.clear()
    # Run core grains
    for key in funcs:
        if not key.startswith("core."):
            continue
        log.trace("Loading %s grain", key)
        ret = funcs[key]()
        if not isinstance(ret, dict):
            continue
        if blist:
            for key in list(ret):
                for block in blist:
                    if salt.utils.stringutils.expr_match(key, block):
                        del ret[key]
                        log.trace("Filtering %s grain", key)
            if not ret:
                continue
        if grains_deep_merge:
            salt.utils.dictupdate.update(grains_data, ret)
        else:
            grains_data.update(ret)

    # Run the rest of the grains
    for key in funcs:
        if key.startswith("core.") or key == "_errors":
            continue
        try:
            # Grains are loaded too early to take advantage of the injected
            # __proxy__ variable.  Pass an instance of that LazyLoader
            # here instead to grains functions if the grains functions take
            # one parameter.  Then the grains can have access to the
            # proxymodule for retrieving information from the connected
            # device.
            log.trace("Loading %s grain", key)
            parameters = salt.utils.args.get_function_argspec(funcs[key]).args
            kwargs = {}
            if "proxy" in parameters:
                kwargs["proxy"] = proxy
            if "grains" in parameters:
                kwargs["grains"] = grains_data
            ret = funcs[key](**kwargs)
        except Exception:  # pylint: disable=broad-except
            if salt.utils.platform.is_proxy():
                log.info(
                    "The following CRITICAL message may not be an error; the proxy may not be completely established yet."
                )
            log.critical(
                "Failed to load grains defined in grain file %s in "
                "function %s, error:\n",
                key,
                funcs[key],
                exc_info=True,
            )
            continue
        if not isinstance(ret, dict):
            continue
        if blist:
            for key in list(ret):
                for block in blist:
                    if salt.utils.stringutils.expr_match(key, block):
                        del ret[key]
                        log.trace("Filtering %s grain", key)
            if not ret:
                continue
        if grains_deep_merge:
            salt.utils.dictupdate.update(grains_data, ret)
        else:
            grains_data.update(ret)

    if opts.get("proxy_merge_grains_in_module", True) and proxy:
        try:
            proxytype = proxy.opts["proxy"]["proxytype"]
            if proxytype + ".grains" in proxy:
                if (
                    proxytype + ".initialized" in proxy
                    and proxy[proxytype + ".initialized"]()
                ):
                    try:
                        proxytype = proxy.opts["proxy"]["proxytype"]
                        ret = proxy[proxytype + ".grains"]()
                        if grains_deep_merge:
                            salt.utils.dictupdate.update(grains_data, ret)
                        else:
                            grains_data.update(ret)
                    except Exception:  # pylint: disable=broad-except
                        log.critical(
                            "Failed to run proxy's grains function!", exc_info=True
                        )
        except KeyError:
            pass

    grains_data.update(opts["grains"])
    # Write cache if enabled
    if opts.get("grains_cache", False):
        with salt.utils.files.set_umask(0o077):
            try:
                if salt.utils.platform.is_windows():
                    # Late import
                    import salt.modules.cmdmod

                    # Make sure cache file isn't read-only
                    salt.modules.cmdmod._run_quiet('attrib -R "{}"'.format(cfn))
                with salt.utils.files.fopen(cfn, "w+b") as fp_:
                    try:
                        salt.payload.dump(grains_data, fp_)
                    except TypeError as e:
                        log.error("Failed to serialize grains cache: %s", e)
                        raise  # re-throw for cleanup
            except Exception as e:  # pylint: disable=broad-except
                log.error("Unable to write to grains cache file %s: %s", cfn, e)
                # Based on the original exception, the file may or may not have been
                # created. If it was, we will remove it now, as the exception means
                # the serialized data is not to be trusted, no matter what the
                # exception is.
                if os.path.isfile(cfn):
                    os.unlink(cfn)

    if grains_deep_merge:
        salt.utils.dictupdate.update(grains_data, opts["grains"])
    else:
        grains_data.update(opts["grains"])
    return salt.utils.data.decode(grains_data, preserve_tuples=True)


# TODO: get rid of? Does anyone use this? You should use raw() instead
def call(fun, **kwargs):
    """
    Directly call a function inside a loader directory
    """
    args = kwargs.get("args", [])
    dirs = kwargs.get("dirs", [])

    funcs = LazyLoader(
        [str(SALT_BASE_PATH / "modules")] + dirs,
        None,
        tag="modules",
        virtual_enable=False,
    )
    return funcs[fun](*args)


def runner(opts, utils=None, context=None, whitelist=None):
    """
    Directly call a function inside a loader directory
    """
    if utils is None:
        utils = {}
    if context is None:
        context = {}
    return LazyLoader(
        _module_dirs(opts, "runners", "runner", ext_type_dirs="runner_dirs"),
        opts,
        tag="runners",
        pack={"__utils__": utils, "__context__": context},
        whitelist=whitelist,
        extra_module_dirs=utils.module_dirs if utils else None,
        # TODO: change from __salt__ to something else, we overload __salt__ too much
        pack_self="__salt__",
    )


def queues(opts):
    """
    Directly call a function inside a loader directory
    """
    return LazyLoader(
        _module_dirs(opts, "queues", "queue", ext_type_dirs="queue_dirs"),
        opts,
        tag="queues",
    )


def sdb(opts, functions=None, whitelist=None, utils=None):
    """
    Make a very small database call
    """
    if utils is None:
        utils = {}

    return LazyLoader(
        _module_dirs(opts, "sdb"),
        opts,
        tag="sdb",
        pack={
            "__sdb__": functions,
            "__utils__": utils,
            "__salt__": minion_mods(opts, utils=utils),
        },
        whitelist=whitelist,
        extra_module_dirs=utils.module_dirs if utils else None,
    )


def pkgdb(opts):
    """
    Return modules for SPM's package database

    .. versionadded:: 2015.8.0
    """
    return LazyLoader(
        _module_dirs(opts, "pkgdb", base_path=str(SALT_BASE_PATH / "spm")),
        opts,
        tag="pkgdb",
    )


def pkgfiles(opts):
    """
    Return modules for SPM's file handling

    .. versionadded:: 2015.8.0
    """
    return LazyLoader(
        _module_dirs(opts, "pkgfiles", base_path=str(SALT_BASE_PATH / "spm")),
        opts,
        tag="pkgfiles",
    )


def clouds(opts):
    """
    Return the cloud functions
    """
    _utils = utils(opts)
    # Let's bring __active_provider_name__, defaulting to None, to all cloud
    # drivers. This will get temporarily updated/overridden with a context
    # manager when needed.
    functions = LazyLoader(
        _module_dirs(
            opts,
            "clouds",
            "cloud",
            base_path=str(SALT_BASE_PATH / "cloud"),
            int_type="clouds",
        ),
        opts,
        tag="clouds",
        pack={"__utils__": _utils, "__active_provider_name__": None},
        extra_module_dirs=_utils.module_dirs,
    )
    for funcname in LIBCLOUD_FUNCS_NOT_SUPPORTED:
        log.trace(
            "'%s' has been marked as not supported. Removing from the "
            "list of supported cloud functions",
            funcname,
        )
        functions.pop(funcname, None)
    return functions


def netapi(opts):
    """
    Return the network api functions
    """
    return LazyLoader(
        _module_dirs(opts, "netapi"),
        opts,
        tag="netapi",
    )


def executors(opts, functions=None, context=None, proxy=None):
    """
    Returns the executor modules
    """
    if proxy is None:
        proxy = {}
    if context is None:
        context = {}
    return LazyLoader(
        _module_dirs(opts, "executors", "executor"),
        opts,
        tag="executor",
        pack={"__salt__": functions, "__context__": context, "__proxy__": proxy},
        pack_self="__executors__",
    )


def cache(opts):
    """
    Returns the returner modules
    """
    return LazyLoader(
        _module_dirs(opts, "cache", "cache"),
        opts,
        tag="cache",
    )


@contextlib.contextmanager
def catch_entry_points_exception(entry_point):
    context = types.SimpleNamespace(exception_caught=False)
    try:
        yield context
    except Exception as exc:  # pylint: disable=broad-except
        context.exception_caught = True
        entry_point_details = entrypoints.name_and_version_from_entry_point(entry_point)
        log.error(
            "Error processing Salt Extension %s(version: %s): %s",
            entry_point_details.name,
            entry_point_details.version,
            exc,
            exc_info_on_loglevel=logging.DEBUG,
        )
