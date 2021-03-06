"""
The Salt loader is the core to Salt's plugin system, the loader scans
directories for python loadable code and organizes the code into the
plugin interfaces used by Salt.
"""

import contextvars
import copy
import functools
import importlib
import importlib.machinery  # pylint: disable=no-name-in-module,import-error
import importlib.util  # pylint: disable=no-name-in-module,import-error
import inspect
import logging
import os
import re
import sys
import tempfile
import threading
import time
import traceback
import types
from collections.abc import MutableMapping
from contextlib import contextmanager
from zipimport import zipimporter

import salt.config
import salt.defaults.events
import salt.defaults.exitcodes
import salt.loader_context
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
from salt.utils.decorators import Depends

log = logging.getLogger(__name__)

SALT_BASE_PATH = os.path.abspath(salt.syspaths.INSTALL_DIR)
LOADED_BASE_NAME = "salt.loaded"

# pylint: disable=no-member
MODULE_KIND_SOURCE = 1
MODULE_KIND_COMPILED = 2
MODULE_KIND_EXTENSION = 3
MODULE_KIND_PKG_DIRECTORY = 5
SUFFIXES = []
for suffix in importlib.machinery.EXTENSION_SUFFIXES:
    SUFFIXES.append((suffix, "rb", MODULE_KIND_EXTENSION))
for suffix in importlib.machinery.SOURCE_SUFFIXES:
    SUFFIXES.append((suffix, "rb", MODULE_KIND_SOURCE))
for suffix in importlib.machinery.BYTECODE_SUFFIXES:
    SUFFIXES.append((suffix, "rb", MODULE_KIND_COMPILED))
MODULE_KIND_MAP = {
    MODULE_KIND_SOURCE: importlib.machinery.SourceFileLoader,
    MODULE_KIND_COMPILED: importlib.machinery.SourcelessFileLoader,
    MODULE_KIND_EXTENSION: importlib.machinery.ExtensionFileLoader,
}
# pylint: enable=no-member

PY3_PRE_EXT = re.compile(r"\.cpython-{}{}(\.opt-[1-9])?".format(*sys.version_info[:2]))

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
            opts, ext_type, tag, int_type, ext_dirs, ext_type_dirs, base_path,
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
    ext_types = os.path.join(opts["extension_modules"], ext_type)

    ext_type_types = []
    if ext_dirs:
        if ext_type_dirs is None:
            ext_type_dirs = "{}_dirs".format(tag)
        if ext_type_dirs in opts:
            ext_type_types.extend(opts[ext_type_dirs])
        if ext_type_dirs:
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

                    if isinstance(loaded_entry_point_value, list):
                        # This is old style entry-point, and, as such, the entry point name MUST
                        # match the value of `ext_type_dirs
                        if entry_point.name != ext_type_dirs:
                            continue
                        for path in loaded_entry_point_value:
                            loaded_entry_point_paths.add(path)
                    elif isinstance(loaded_entry_point_value, dict):
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

    loader._load_module(name)  # load a single module (the one passed in)
    return dict(loader._dict)  # return a copy of *just* the funcs for `name`


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


def utils(opts, whitelist=None, context=None, proxy=proxy, pack_self=None):
    """
    Returns the utility modules
    """
    return LazyLoader(
        _module_dirs(opts, "utils", ext_type_dirs="utils_dirs"),
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
        _module_dirs(opts, "tops", "top"), opts, tag="top", whitelist=whitelist,
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
    return LazyLoader(_module_dirs(opts, "serializers"), opts, tag="serializers",)


def eauth_tokens(opts):
    """
    Returns the tokens modules
    :param dict opts: The Salt options dictionary
    :returns: LazyLoader instance, with only token backends present in the keyspace
    """
    return LazyLoader(_module_dirs(opts, "tokens"), opts, tag="tokens",)


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
            base_path=os.path.join(SALT_BASE_PATH, "log"),
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
            base_path=os.path.join(SALT_BASE_PATH, os.path.join("client", "ssh")),
        ),
        opts,
        tag="wrapper",
        pack={
            "__salt__": functions,
            #        "__grains__": opts.get("grains", {}),
            #        "__pillar__": opts.get("pillar", {}),
            "__context__": context,
        },
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
        _module_dirs(opts, "renderers", "render", ext_type_dirs="render_dirs",),
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
        _module_dirs(opts, "grains", "grain", ext_type_dirs="grains_dirs",),
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
        serial = salt.payload.Serial(opts)
        with salt.utils.files.fopen(cfn, "rb") as fp_:
            cached_grains = salt.utils.data.decode(
                serial.load(fp_), preserve_tuples=True
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
                        serial = salt.payload.Serial(opts)
                        serial.dump(grains_data, fp_)
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
        [os.path.join(SALT_BASE_PATH, "modules")] + dirs,
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
        _module_dirs(opts, "pkgdb", base_path=os.path.join(SALT_BASE_PATH, "spm")),
        opts,
        tag="pkgdb",
    )


def pkgfiles(opts):
    """
    Return modules for SPM's file handling

    .. versionadded:: 2015.8.0
    """
    return LazyLoader(
        _module_dirs(opts, "pkgfiles", base_path=os.path.join(SALT_BASE_PATH, "spm")),
        opts,
        tag="pkgfiles",
    )


def clouds(opts):
    """
    Return the cloud functions
    """
    _utils = salt.loader.utils(opts)
    # Let's bring __active_provider_name__, defaulting to None, to all cloud
    # drivers. This will get temporarily updated/overridden with a context
    # manager when needed.
    functions = LazyLoader(
        _module_dirs(
            opts,
            "clouds",
            "cloud",
            base_path=os.path.join(SALT_BASE_PATH, "cloud"),
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
    return LazyLoader(_module_dirs(opts, "netapi"), opts, tag="netapi",)


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


def cache(opts, serial):
    """
    Returns the returner modules
    """
    return LazyLoader(
        _module_dirs(opts, "cache", "cache"),
        opts,
        tag="cache",
        pack={"__context__": {"serial": serial}},
    )


def _generate_module(name):
    if name in sys.modules:
        return

    code = "'''Salt loaded {} parent module'''".format(name.split(".")[-1])
    # ModuleType can't accept a unicode type on PY2
    module = types.ModuleType(str(name))  # future lint: disable=blacklisted-function
    exec(code, module.__dict__)
    sys.modules[name] = module


def _mod_type(module_path):
    if module_path.startswith(SALT_BASE_PATH):
        return "int"
    return "ext"


# TODO: move somewhere else?
class FilterDictWrapper(MutableMapping):
    """
    Create a dict which wraps another dict with a specific key suffix on get

    This is to replace "filter_load"
    """

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
                yield key.replace(self.suffix, "")


class LoadedFunc:
    """
    The functions loaded by LazyLoader instances using subscript notation
    'a[k]' will be wrapped with LoadedFunc.

      - Makes sure functions are called with the correct loader's context.
      - Provides access to a wrapped func's __global__ attribute

    :param func callable: The callable to wrap.
    :param dict loader: The loader to use in the context when the wrapped callable is called.
    """

    def __init__(self, func, loader):
        self.func = func
        self.loader = loader
        functools.update_wrapper(self, func)

    def __getattr__(self, name):
        return getattr(self.func, name)

    def __call__(self, *args, **kwargs):
        if self.loader.inject_globals:
            run_func = global_injector_decorator(self.loader.inject_globals)(self.func)
        else:
            run_func = self.func
        return self.loader.run(run_func, *args, **kwargs)


class LoadedMod:
    def __init__(self, mod, loader):
        """
        Return the wrapped func's globals via this object's __globals__
        attribute.
        """
        self.mod = mod
        self.loader = loader

    def __getattr__(self, name):
        """
        Run the wrapped function in the loader's context.
        """
        attr = getattr(self.mod, name)
        if inspect.isfunction(attr) or inspect.ismethod(attr):
            return LoadedFunc(attr, self.loader)
        return attr


class LazyLoader(salt.utils.lazy.LazyDict):
    """
    A pseduo-dictionary which has a set of keys which are the
    name of the module and function, delimited by a dot. When
    the value of the key is accessed, the function is then loaded
    from disk and into memory.

    .. note::

        Iterating over keys will cause all modules to be loaded.

    :param list module_dirs: A list of directories on disk to search for modules
    :param dict opts: The salt options dictionary.
    :param str tag: The tag for the type of module to load
    :param func mod_type_check: A function which can be used to verify files
    :param dict pack: A dictionary of function to be packed into modules as they are loaded
    :param list whitelist: A list of modules to whitelist
    :param bool virtual_enable: Whether or not to respect the __virtual__ function when loading modules.
    :param str virtual_funcs: The name of additional functions in the module to call to verify its functionality.
                                If not true, the module will not load.
    :param list extra_module_dirs: A list of directories that will be able to import from
    :param str pack_self: Pack this module into a variable by this name into modules loaded
    :returns: A LazyLoader object which functions as a dictionary. Keys are 'module.function' and values
    are function references themselves which are loaded on-demand.
    # TODO:
        - move modules_max_memory into here
        - singletons (per tag)
    """

    mod_dict_class = salt.utils.odict.OrderedDict

    def __init__(
        self,
        module_dirs,
        opts=None,
        tag="module",
        loaded_base_name=None,
        mod_type_check=None,
        pack=None,
        whitelist=None,
        virtual_enable=True,
        static_modules=None,
        proxy=None,
        virtual_funcs=None,
        extra_module_dirs=None,
        pack_self=None,
    ):  # pylint: disable=W0231
        """
        In pack, if any of the values are None they will be replaced with an
        empty context-specific dict
        """

        self.parent_loader = None
        self.inject_globals = {}
        self.pack = {} if pack is None else pack
        for i in self.pack:
            if isinstance(self.pack[i], salt.loader_context.NamedLoaderContext):
                self.pack[i] = self.pack[i].value()
        if opts is None:
            opts = {}
        threadsafety = not opts.get("multiprocessing")
        self.context_dict = salt.utils.context.ContextDict(threadsafe=threadsafety)
        self.opts = self.__prep_mod_opts(opts)
        self.pack_self = pack_self

        self.module_dirs = module_dirs
        self.tag = tag
        self._gc_finalizer = None
        if loaded_base_name and loaded_base_name != LOADED_BASE_NAME:
            self.loaded_base_name = loaded_base_name
        else:
            self.loaded_base_name = LOADED_BASE_NAME
        self.mod_type_check = mod_type_check or _mod_type

        if "__context__" not in self.pack:
            self.pack["__context__"] = None

        for k, v in self.pack.items():
            if v is None:  # if the value of a pack is None, lets make an empty dict
                self.context_dict.setdefault(k, {})
                self.pack[k] = salt.utils.context.NamespacedDictWrapper(
                    self.context_dict, k
                )

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

        self.extra_module_dirs = extra_module_dirs if extra_module_dirs else []
        self._clean_module_dirs = []

        self.disabled = set(
            self.opts.get(
                "disable_{}{}".format(self.tag, "" if self.tag[-1] == "s" else "s"), [],
            )
        )

        # A map of suffix to description for imp
        self.suffix_map = {}
        # A list to determine precedence of extensions
        # Prefer packages (directories) over modules (single files)!
        self.suffix_order = [""]
        for (suffix, mode, kind) in SUFFIXES:
            self.suffix_map[suffix] = (suffix, mode, kind)
            self.suffix_order.append(suffix)

        self._lock = threading.RLock()
        with self._lock:
            self._refresh_file_mapping()

        super().__init__()  # late init the lazy loader
        # create all of the import namespaces
        _generate_module("{}.int".format(self.loaded_base_name))
        _generate_module("{}.int.{}".format(self.loaded_base_name, tag))
        _generate_module("{}.ext".format(self.loaded_base_name))
        _generate_module("{}.ext.{}".format(self.loaded_base_name, tag))

    def clean_modules(self):
        """
        Clean modules
        """
        for name in list(sys.modules):
            if name.startswith(self.loaded_base_name):
                del sys.modules[name]

    def __getitem__(self, item):
        """
        Override the __getitem__ in order to decorate the returned function if we need
        to last-minute inject globals
        """
        func = super().__getitem__(item)
        return LoadedFunc(func, self)

    def __getattr__(self, mod_name):
        """
        Allow for "direct" attribute access-- this allows jinja templates to
        access things like `salt.test.ping()`
        """
        if mod_name in ("__getstate__", "__setstate__"):
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
            return LoadedMod(self.loaded_modules[mod_name], self)
        else:
            raise AttributeError(mod_name)

    def missing_fun_string(self, function_name):
        """
        Return the error string for a missing function.

        This can range from "not available' to "__virtual__" returned False
        """
        mod_name = function_name.split(".")[0]
        if mod_name in self.loaded_modules:
            return "'{}' is not available.".format(function_name)
        else:
            try:
                reason = self.missing_modules[mod_name]
            except KeyError:
                return "'{}' is not available.".format(function_name)
            else:
                if reason is not None:
                    return "'{}' __virtual__ returned False: {}".format(
                        mod_name, reason
                    )
                else:
                    return "'{}' __virtual__ returned False".format(mod_name)

    def _refresh_file_mapping(self):
        """
        refresh the mapping of the FS on disk
        """
        # map of suffix to description for imp
        if (
            self.opts.get("cython_enable", True) is True
            and ".pyx" not in self.suffix_map
        ):
            try:
                global pyximport
                pyximport = __import__("pyximport")  # pylint: disable=import-error
                pyximport.install()
                # add to suffix_map so file_mapping will pick it up
                self.suffix_map[".pyx"] = tuple()
                if ".pyx" not in self.suffix_order:
                    self.suffix_order.append(".pyx")
            except ImportError:
                log.info(
                    "Cython is enabled in the options but not present "
                    "in the system path. Skipping Cython modules."
                )
        # Allow for zipimport of modules
        if (
            self.opts.get("enable_zip_modules", True) is True
            and ".zip" not in self.suffix_map
        ):
            self.suffix_map[".zip"] = tuple()
            if ".zip" not in self.suffix_order:
                self.suffix_order.append(".zip")
        # allow for module dirs
        self.suffix_map[""] = ("", "", MODULE_KIND_PKG_DIRECTORY)

        # create mapping of filename (without suffix) to (path, suffix)
        # The files are added in order of priority, so order *must* be retained.
        self.file_mapping = salt.utils.odict.OrderedDict()

        opt_match = []

        def _replace_pre_ext(obj):
            """
            Hack so we can get the optimization level that we replaced (if
            any) out of the re.sub call below. We use a list here because
            it is a persistent data structure that we will be able to
            access after re.sub is called.
            """
            opt_match.append(obj)
            return ""

        for mod_dir in self.module_dirs:
            try:
                # Make sure we have a sorted listdir in order to have
                # expectable override results
                files = sorted(x for x in os.listdir(mod_dir) if x != "__pycache__")
            except OSError:
                continue  # Next mod_dir
            try:
                pycache_files = [
                    os.path.join("__pycache__", x)
                    for x in sorted(os.listdir(os.path.join(mod_dir, "__pycache__")))
                ]
            except OSError:
                pass
            else:
                files.extend(pycache_files)

            for filename in files:
                try:
                    dirname, basename = os.path.split(filename)
                    if basename.startswith("_"):
                        # skip private modules
                        # log messages omitted for obviousness
                        continue  # Next filename
                    f_noext, ext = os.path.splitext(basename)
                    f_noext = PY3_PRE_EXT.sub(_replace_pre_ext, f_noext)
                    try:
                        opt_level = int(opt_match.pop().group(1).rsplit("-", 1)[-1])
                    except (AttributeError, IndexError, ValueError):
                        # No regex match or no optimization level matched
                        opt_level = 0
                    try:
                        opt_index = self.opts["optimization_order"].index(opt_level)
                    except KeyError:
                        log.trace(
                            "Disallowed optimization level %d for module "
                            "name '%s', skipping. Add %d to the "
                            "'optimization_order' config option if you "
                            "do not want to ignore this optimization "
                            "level.",
                            opt_level,
                            f_noext,
                            opt_level,
                        )
                        continue

                    # make sure it is a suffix we support
                    if ext not in self.suffix_map:
                        continue  # Next filename
                    if f_noext in self.disabled:
                        log.trace(
                            "Skipping %s, it is disabled by configuration", filename
                        )
                        continue  # Next filename
                    fpath = os.path.join(mod_dir, filename)
                    # if its a directory, lets allow us to load that
                    if ext == "":
                        # is there something __init__?
                        subfiles = os.listdir(fpath)
                        for suffix in self.suffix_order:
                            if "" == suffix:
                                continue  # Next suffix (__init__ must have a suffix)
                            init_file = "__init__{}".format(suffix)
                            if init_file in subfiles:
                                break
                        else:
                            continue  # Next filename

                    try:
                        curr_ext = self.file_mapping[f_noext][1]
                        curr_opt_index = self.file_mapping[f_noext][2]
                    except KeyError:
                        pass
                    else:
                        if "" in (curr_ext, ext) and curr_ext != ext:
                            log.error(
                                "Module/package collision: '%s' and '%s'",
                                fpath,
                                self.file_mapping[f_noext][0],
                            )

                        if ext == ".pyc" and curr_ext == ".pyc":
                            # Check the optimization level
                            if opt_index >= curr_opt_index:
                                # Module name match, but a higher-priority
                                # optimization level was already matched, skipping.
                                continue
                        elif not curr_ext or self.suffix_order.index(
                            ext
                        ) >= self.suffix_order.index(curr_ext):
                            # Match found but a higher-priorty match already
                            # exists, so skip this.
                            continue

                    if not dirname and ext == ".pyc":
                        # On Python 3, we should only load .pyc files from the
                        # __pycache__ subdirectory (i.e. when dirname is not an
                        # empty string).
                        continue

                    # Made it this far - add it
                    self.file_mapping[f_noext] = (fpath, ext, opt_index)

                except OSError:
                    continue
        for smod in self.static_modules:
            f_noext = smod.split(".")[-1]
            self.file_mapping[f_noext] = (smod, ".o", 0)

    def clear(self):
        """
        Clear the dict
        """
        with self._lock:
            super().clear()  # clear the lazy loader
            self.loaded_files = set()
            self.missing_modules = {}
            self.loaded_modules = {}
            # if we have been loaded before, lets clear the file mapping since
            # we obviously want a re-do
            if hasattr(self, "opts"):
                self._refresh_file_mapping()
            self.initial_load = False

    def __prep_mod_opts(self, opts):
        """
        Strip out of the opts any logger instance
        """
        if "__grains__" not in self.pack:
            grains = opts.get("grains", {})
            if isinstance(grains, salt.loader_context.NamedLoaderContext):
                grains = grains.value()
            self.context_dict["grains"] = grains
            self.pack["__grains__"] = salt.utils.context.NamespacedDictWrapper(
                self.context_dict, "grains"
            )

        if "__pillar__" not in self.pack:
            pillar = opts.get("pillar", {})
            if isinstance(pillar, salt.loader_context.NamedLoaderContext):
                pillar = pillar.value()
            self.context_dict["pillar"] = pillar
            self.pack["__pillar__"] = salt.utils.context.NamespacedDictWrapper(
                self.context_dict, "pillar"
            )

        mod_opts = {}
        for key, val in list(opts.items()):
            if key == "logger":
                continue
            mod_opts[key] = val
        return mod_opts

    def _iter_files(self, mod_name):
        """
        Iterate over all file_mapping files in order of closeness to mod_name
        """
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
            getattr(mod, sname)
            for sname in dir(mod)
            if isinstance(getattr(mod, sname), mod.__class__)
        )

        # reload only custom "sub"modules
        for submodule in submodules:
            # it is a submodule if the name is in a namespace under mod
            if submodule.__name__.startswith(mod.__name__ + "."):
                importlib.reload(submodule)
                self._reload_submodules(submodule)

    def __populate_sys_path(self):
        for directory in self.extra_module_dirs:
            if directory not in sys.path:
                sys.path.append(directory)
                self._clean_module_dirs.append(directory)

    def __clean_sys_path(self):
        invalidate_path_importer_cache = False
        for directory in self._clean_module_dirs:
            if directory in sys.path:
                sys.path.remove(directory)
                invalidate_path_importer_cache = True
        self._clean_module_dirs = []

        # Be sure that sys.path_importer_cache do not contains any
        # invalid FileFinder references
        importlib.invalidate_caches()

        # Because we are mangling with importlib, we can find from
        # time to time an invalidation issue with
        # sys.path_importer_cache, that requires the removal of
        # FileFinder that remain None for the extra_module_dirs
        if invalidate_path_importer_cache:
            for directory in self.extra_module_dirs:
                if (
                    directory in sys.path_importer_cache
                    and sys.path_importer_cache[directory] is None
                ):
                    del sys.path_importer_cache[directory]

    def _load_module(self, name):
        mod = None
        fpath, suffix = self.file_mapping[name][:2]
        # if the fpath has `.cpython-3x` in it, but the running Py version
        # is 3.y, the following will cause us to return immediately and we won't try to import this .pyc.
        # This is for the unusual case where several Python versions share a single
        # source tree and drop their .pycs in the same __pycache__ folder.
        # If we were to load a .pyc for another Py version it's not a big problem
        # but the log will get spammed with "Bad Magic Number" messages that
        # can be very misleading if the user is debugging another problem.
        try:
            (implementation_tag, cache_tag_ver) = sys.implementation.cache_tag.split(
                "-"
            )
            if cache_tag_ver not in fpath and implementation_tag in fpath:
                log.trace(
                    "Trying to load %s on %s, returning False.",
                    fpath,
                    sys.implementation.cache_tag,
                )
                return False
        except AttributeError:
            # Most likely Py 2.7 or some other Python version we don't really support
            pass

        self.loaded_files.add(name)
        fpath_dirname = os.path.dirname(fpath)
        try:
            self.__populate_sys_path()
            sys.path.append(fpath_dirname)
            if suffix == ".pyx":
                mod = pyximport.load_module(name, fpath, tempfile.gettempdir())
            elif suffix == ".o":
                top_mod = __import__(fpath, globals(), locals(), [])
                comps = fpath.split(".")
                if len(comps) < 2:
                    mod = top_mod
                else:
                    mod = top_mod
                    for subname in comps[1:]:
                        mod = getattr(mod, subname)
            elif suffix == ".zip":
                mod = zipimporter(fpath).load_module(name)
            else:
                desc = self.suffix_map[suffix]
                # if it is a directory, we don't open a file
                try:
                    mod_namespace = ".".join(
                        (
                            self.loaded_base_name,
                            self.mod_type_check(fpath),
                            self.tag,
                            name,
                        )
                    )
                except TypeError:
                    mod_namespace = "{}.{}.{}.{}".format(
                        self.loaded_base_name,
                        self.mod_type_check(fpath),
                        self.tag,
                        name,
                    )
                if suffix == "":
                    # pylint: disable=no-member
                    # Package directory, look for __init__
                    loader_details = [
                        (
                            importlib.machinery.SourceFileLoader,
                            importlib.machinery.SOURCE_SUFFIXES,
                        ),
                        (
                            importlib.machinery.SourcelessFileLoader,
                            importlib.machinery.BYTECODE_SUFFIXES,
                        ),
                        (
                            importlib.machinery.ExtensionFileLoader,
                            importlib.machinery.EXTENSION_SUFFIXES,
                        ),
                    ]
                    file_finder = importlib.machinery.FileFinder(
                        fpath_dirname, *loader_details
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
                    # reload all submodules if necessary
                    if not self.initial_load:
                        self._reload_submodules(mod)
                else:
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
                    mod = self.run(spec.loader.load_module)
                    # mod = importlib.util.module_from_spec(spec)
                    # spec.loader.exec_module(mod)
                    # pylint: enable=no-member
                    sys.modules[mod_namespace] = mod
        except OSError:
            raise
        except ImportError as exc:
            if "magic number" in str(exc):
                error_msg = "Failed to import {} {}. Bad magic number. If migrating from Python2 to Python3, remove all .pyc files and try again.".format(
                    self.tag, name
                )
                log.warning(error_msg)
                self.missing_modules[name] = error_msg
            log.debug("Failed to import %s %s:\n", self.tag, name, exc_info=True)
            self.missing_modules[name] = exc
            return False
        except Exception as error:  # pylint: disable=broad-except
            log.error(
                "Failed to import %s %s, this is due most likely to a "
                "syntax error:\n",
                self.tag,
                name,
                exc_info=True,
            )
            self.missing_modules[name] = error
            return False
        except SystemExit as error:
            try:
                fn_, _, caller, _ = traceback.extract_tb(sys.exc_info()[2])[-1]
            except Exception:  # pylint: disable=broad-except
                pass
            else:
                tgt_fns = [
                    os.path.join("salt", "utils", "process.py"),
                    os.path.join("salt", "cli", "daemons.py"),
                    os.path.join("salt", "cli", "api.py"),
                ]
                for tgt_fn in tgt_fns:
                    if fn_.endswith(tgt_fn) and "_handle_signals" in caller:
                        # Race conditon, SIGTERM or SIGINT received while loader
                        # was in process of loading a module. Call sys.exit to
                        # ensure that the process is killed.
                        sys.exit(salt.defaults.exitcodes.EX_OK)
            log.error(
                "Failed to import %s %s as the module called exit()\n",
                self.tag,
                name,
                exc_info=True,
            )
            self.missing_modules[name] = error
            return False
        finally:
            sys.path.remove(fpath_dirname)
            self.__clean_sys_path()

        loader_context = salt.loader_context.LoaderContext()
        if hasattr(mod, "__salt_loader__"):
            if not isinstance(mod.__salt_loader__, salt.loader_context.LoaderContext):
                log.warning("Override  __salt_loader__: %s", mod)
                mod.__salt_loader__ = loader_context
        else:
            mod.__salt_loader__ = loader_context

        if hasattr(mod, "__opts__"):
            if not isinstance(mod.__opts__, salt.loader_context.NamedLoaderContext):
                if not hasattr(mod, "__orig_opts__"):
                    mod.__orig_opts__ = copy.deepcopy(mod.__opts__)
                mod.__opts__ = copy.deepcopy(mod.__orig_opts__)
                mod.__opts__.update(self.opts)
        else:
            if not hasattr(mod, "__orig_opts__"):
                mod.__orig_opts__ = {}
            mod.__opts__ = copy.deepcopy(mod.__orig_opts__)
            mod.__opts__.update(self.opts)

        # pack whatever other globals we were asked to
        for p_name, p_value in self.pack.items():
            mod_named_context = getattr(mod, p_name, None)
            if hasattr(mod_named_context, "default"):
                default = copy.deepcopy(mod_named_context.default)
            else:
                default = None
            named_context = loader_context.named_context(p_name, default)
            if mod_named_context is None:
                setattr(mod, p_name, named_context)
            elif named_context != mod_named_context:
                log.debug("Override  %s: %s", p_name, mod)
                setattr(mod, p_name, named_context)
            else:
                setattr(mod, p_name, named_context)

        if self.pack_self is not None:
            mod_named_context = getattr(mod, self.pack_self, None)
            if hasattr(mod_named_context, "default"):
                default = copy.deepcopy(mod_named_context.default)
            else:
                default = None
            named_context = loader_context.named_context(self.pack_self, default)
            if mod_named_context is None:
                setattr(mod, self.pack_self, named_context)
            elif named_context != mod_named_context:
                log.debug("Override  %s: %s", self.pack_self, mod)
                setattr(mod, self.pack_self, named_context)
            else:
                setattr(mod, self.pack_self, named_context)

        module_name = mod.__name__.rsplit(".", 1)[-1]

        # Call a module's initialization method if it exists
        module_init = getattr(mod, "__init__", None)
        if inspect.isfunction(module_init):
            try:
                self.run(module_init, self.opts)
            except TypeError as e:
                log.error(e)
            except Exception:  # pylint: disable=broad-except
                err_string = "__init__ failed"
                log.debug(
                    "Error loading %s.%s: %s",
                    self.tag,
                    module_name,
                    err_string,
                    exc_info=True,
                )
                self.missing_modules[module_name] = err_string
                self.missing_modules[name] = err_string
                return False

        # if virtual modules are enabled, we need to look for the
        # __virtual__() function inside that module and run it.
        if self.virtual_enable:
            virtual_funcs_to_process = ["__virtual__"] + self.virtual_funcs
            for virtual_func in virtual_funcs_to_process:
                (
                    virtual_ret,
                    module_name,
                    virtual_err,
                    virtual_aliases,
                ) = self._process_virtual(mod, module_name, virtual_func)
                if virtual_err is not None:
                    log.trace(
                        "Error loading %s.%s: %s", self.tag, module_name, virtual_err
                    )

                # if _process_virtual returned a non-True value then we are
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
        if "proxy" in self.opts:
            if self.tag in ["grains", "proxy"]:
                if not hasattr(mod, "__proxyenabled__") or (
                    self.opts["proxy"]["proxytype"] not in mod.__proxyenabled__
                    and "*" not in mod.__proxyenabled__
                ):
                    err_string = "not a proxy_minion enabled module"
                    self.missing_modules[module_name] = err_string
                    self.missing_modules[name] = err_string
                    return False

        if getattr(mod, "__load__", False) is not False:
            log.info(
                "The functions from module '%s' are being loaded from the "
                "provided __load__ attribute",
                module_name,
            )

        # If we had another module by the same virtual name, we should put any
        # new functions under the existing dictionary.
        mod_names = [module_name] + list(virtual_aliases)
        mod_dict = {
            x: self.loaded_modules.get(x, self.mod_dict_class()) for x in mod_names
        }

        for attr in getattr(mod, "__load__", dir(mod)):
            if attr.startswith("_"):
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
            funcname = getattr(mod, "__func_alias__", {}).get(attr, attr)
            for tgt_mod in mod_names:
                try:
                    full_funcname = ".".join((tgt_mod, funcname))
                except TypeError:
                    full_funcname = "{}.{}".format(tgt_mod, funcname)
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
            Depends.enforce_dependencies(self._dict, self.tag, name)
        except RuntimeError as exc:
            log.info(
                "Depends.enforce_dependencies() failed for the following " "reason: %s",
                exc,
            )

        for tgt_mod in mod_names:
            self.loaded_modules[tgt_mod] = mod_dict[tgt_mod]
        return True

    def _load(self, key):
        """
        Load a single item if you have it
        """
        # if the key doesn't have a '.' then it isn't valid for this mod dict
        if not isinstance(key, str):
            raise KeyError("The key must be a string.")
        if "." not in key:
            raise KeyError("The key '{}' should contain a '.'".format(key))
        mod_name, _ = key.split(".", 1)
        with self._lock:
            # It is possible that the key is in the dictionary after
            # acquiring the lock due to another thread loading it.
            if mod_name in self.missing_modules or key in self._dict:
                return True
            # if the modulename isn't in the whitelist, don't bother
            if self.whitelist and mod_name not in self.whitelist:
                log.error(
                    "Failed to load function %s because its module (%s) is "
                    "not in the whitelist: %s",
                    key,
                    mod_name,
                    self.whitelist,
                )
                raise KeyError(key)

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
                        self._refresh_file_mapping()
                        reloaded = True
                        continue
                    break
                except OSError:
                    if not reloaded:
                        self._refresh_file_mapping()
                        reloaded = True
                    continue

        return ret

    def _load_all(self):
        """
        Load all of them
        """
        with self._lock:
            for name in self.file_mapping:
                if name in self.loaded_files or name in self.missing_modules:
                    continue
                self._load_module(name)

            self.loaded = True

    def reload_modules(self):
        with self._lock:
            self.loaded_files = set()
            self._load_all()

    def _apply_outputter(self, func, mod):
        """
        Apply the __outputter__ variable to the functions
        """
        if hasattr(mod, "__outputter__"):
            outp = mod.__outputter__
            if func.__name__ in outp:
                func.__outputter__ = outp[func.__name__]

    def _process_virtual(self, mod, module_name, virtual_func="__virtual__"):
        """
        Given a loaded module and its default name determine its virtual name

        This function returns a tuple. The first value will be either True or
        False and will indicate if the module should be loaded or not (i.e. if
        it threw and exception while processing its __virtual__ function). The
        second value is the determined virtual name, which may be the same as
        the value provided.

        The default name can be calculated as follows::

            module_name = mod.__name__.rsplit('.', 1)[-1]
        """

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
        virtual_aliases = getattr(mod, "__virtual_aliases__", tuple())
        try:
            error_reason = None
            if hasattr(mod, "__virtual__") and inspect.isfunction(mod.__virtual__):
                try:
                    start = time.time()
                    virtual_attr = getattr(mod, virtual_func)
                    virtual = self.run(virtual_attr)
                    if isinstance(virtual, tuple):
                        error_reason = virtual[1]
                        virtual = virtual[0]
                    if self.opts.get("virtual_timer", False):
                        end = time.time() - start
                        msg = "Virtual function took {} seconds for {}".format(
                            end, module_name
                        )
                        log.warning(msg)
                except Exception as exc:  # pylint: disable=broad-except
                    error_reason = (
                        "Exception raised when processing __virtual__ function"
                        " for {}. Module will not be loaded: {}".format(
                            mod.__name__, exc
                        )
                    )
                    log.error(error_reason, exc_info_on_loglevel=logging.DEBUG)
                    virtual = None
                # Get the module's virtual name
                virtualname = getattr(mod, "__virtualname__", virtual)
                if not virtual:
                    # if __virtual__() evaluates to False then the module
                    # wasn't meant for this platform or it's not supposed to
                    # load for some other reason.

                    # Some modules might accidentally return None and are
                    # improperly loaded
                    if virtual is None:
                        log.warning(
                            "%s.__virtual__() is wrongly returning `None`. "
                            "It should either return `True`, `False` or a new "
                            "name. If you're the developer of the module "
                            "'%s', please fix this.",
                            mod.__name__,
                            module_name,
                        )

                    return (False, module_name, error_reason, virtual_aliases)

                # At this point, __virtual__ did not return a
                # boolean value, let's check for deprecated usage
                # or module renames
                if virtual is not True and module_name != virtual:
                    # The module is renaming itself. Updating the module name
                    # with the new name
                    log.trace("Loaded %s as virtual %s", module_name, virtual)

                    if virtualname != virtual:
                        # The __virtualname__ attribute does not match what's
                        # being returned by the __virtual__() function. This
                        # should be considered an error.
                        log.error(
                            "The module '%s' is showing some bad usage. Its "
                            "__virtualname__ attribute is set to '%s' yet the "
                            "__virtual__() function is returning '%s'. These "
                            "values should match!",
                            mod.__name__,
                            virtualname,
                            virtual,
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
            log.debug("KeyError when loading %s", module_name, exc_info=True)

        except Exception:  # pylint: disable=broad-except
            # If the module throws an exception during __virtual__()
            # then log the information and continue to the next.
            log.error(
                "Failed to read the virtual function for %s: %s",
                self.tag,
                module_name,
                exc_info=True,
            )
            return (False, module_name, error_reason, virtual_aliases)

        return (True, module_name, None, virtual_aliases)

    def run(self, _func_or_method, *args, **kwargs):
        """
        Run the `_func_or_method` in this loader's context
        """
        self._last_context = contextvars.copy_context()
        return self._last_context.run(self._run_as, _func_or_method, *args, **kwargs)

    def _run_as(self, _func_or_method, *args, **kwargs):
        """
        Handle setting up the context properly and call the method
        """
        self.parent_loader = None
        try:
            current_loader = salt.loader_context.loader_ctxvar.get()
        except LookupError:
            current_loader = None
        if current_loader is not self:
            self.parent_loader = current_loader
        token = salt.loader_context.loader_ctxvar.set(self)
        try:
            return _func_or_method(*args, **kwargs)
        finally:
            self.parent_loader = None
            salt.loader_context.loader_ctxvar.reset(token)

    def run_in_thread(self, _func_or_method, *args, **kwargs):
        """
        Run the function in a new thread with the context of this loader
        """
        argslist = [self, _func_or_method]
        argslist.extend(args)
        thread = threading.Thread(target=self.target, args=argslist, kwargs=kwargs)
        thread.start()
        return thread

    @staticmethod
    def target(loader, _func_or_method, *args, **kwargs):
        loader.run(_func_or_method, *args, **kwargs)


def global_injector_decorator(inject_globals):
    """
    Decorator used by the LazyLoader to inject globals into a function at
    execute time.

    globals
        Dictionary with global variables to inject
    """

    def inner_decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            with salt.utils.context.func_globals_inject(f, **inject_globals):
                return f(*args, **kwargs)

        return wrapper

    return inner_decorator


@contextmanager
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
