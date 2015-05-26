# -*- coding: utf-8 -*-
'''
Routines to set up a minion
'''

from __future__ import absolute_import

# Import python libs
import os
import imp
import sys
import salt
import logging
import inspect
import tempfile
import time

from collections import MutableMapping

# Import salt libs
from salt.exceptions import LoaderError
from salt.template import check_render_pipe_str
from salt.utils.decorators import Depends
import salt.utils.lazy
import salt.utils.odict

# Solve the Chicken and egg problem where grains need to run before any
# of the modules are loaded and are generally available for any usage.
import salt.modules.cmdmod

# Import 3rd-party libs
import salt.ext.six as six

__salt__ = {
    'cmd.run': salt.modules.cmdmod._run_quiet
}
log = logging.getLogger(__name__)

SALT_BASE_PATH = os.path.abspath(os.path.dirname(salt.__file__))
LOADED_BASE_NAME = 'salt.loaded'

# Because on the cloud drivers we do `from salt.cloud.libcloudfuncs import *`
# which simplifies code readability, it adds some unsupported functions into
# the driver's module scope.
# We list un-supported functions here. These will be removed from the loaded.
LIBCLOUD_FUNCS_NOT_SUPPORTED = (
    'parallels.avail_sizes',
    'parallels.avail_locations',
    'proxmox.avail_sizes',
    'saltify.destroy',
    'saltify.avail_sizes',
    'saltify.avail_images',
    'saltify.avail_locations',
    'rackspace.reboot',
    'openstack.list_locations',
    'rackspace.list_locations'
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
    funcs = LazyLoader(_module_dirs(opts,
                                  ext_type,
                                  tag,
                                  int_type,
                                  ext_dirs,
                                  ext_type_dirs,
                                  base_path),
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
        tag,
        int_type=None,
        ext_dirs=True,
        ext_type_dirs=None,
        base_path=None,
        ):
    sys_types = os.path.join(base_path or SALT_BASE_PATH, int_type or ext_type)
    ext_types = os.path.join(opts['extension_modules'], ext_type)

    ext_type_types = []
    if ext_dirs:
        if ext_type_dirs is None:
            ext_type_dirs = '{0}_dirs'.format(tag)
        if ext_type_dirs in opts:
            ext_type_types.extend(opts[ext_type_dirs])

    cli_module_dirs = []
    # The dirs can be any module dir, or a in-tree _{ext_type} dir
    for _dir in opts.get('module_dirs', []):
        # Prepend to the list to match cli argument ordering
        maybe_dir = os.path.join(_dir, ext_type)
        if os.path.isdir(maybe_dir):
            cli_module_dirs.insert(0, maybe_dir)
            continue

        maybe_dir = os.path.join(_dir, '_{0}'.format(ext_type))
        if os.path.isdir(maybe_dir):
            cli_module_dirs.insert(0, maybe_dir)

    return cli_module_dirs + ext_type_types + [ext_types, sys_types]


def minion_mods(
        opts,
        context=None,
        whitelist=None,
        include_errors=False,
        initial_load=False,
        loaded_base_name=None):
    '''
    Load execution modules

    Returns a dictionary of execution modules appropriate for the current
    system by evaluating the __virtual__() function in each module.

    .. code-block:: python

        import salt.config
        import salt.loader

        __opts__ = salt.config.minion_config('/etc/salt/minion')
        __grains__ = salt.loader.grains(__opts__)
        __opts__['grains'] = __grains__
        __salt__ = salt.loader.minion_mods(__opts__)
        __salt__['test.ping']()
    '''
    if context is None:
        context = {}
    if not whitelist:
        whitelist = opts.get('whitelist_modules', None)
    ret = LazyLoader(_module_dirs(opts, 'modules', 'module'),
                     opts,
                     tag='module',
                     pack={'__context__': context},
                     whitelist=whitelist,
                     loaded_base_name=loaded_base_name)

    # Load any provider overrides from the configuration file providers option
    #  Note: Providers can be pkg, service, user or group - not to be confused
    #        with cloud providers.
    providers = opts.get('providers', False)
    if providers and isinstance(providers, dict):
        for mod in providers:
            # sometimes providers opts is not to diverge modules but
            # for other configuration
            try:
                funcs = raw_mod(opts, providers[mod], ret.items())
            except TypeError:
                break
            else:
                if funcs:
                    for func in funcs:
                        f_key = '{0}{1}'.format(mod, func[func.rindex('.'):])
                        ret[f_key] = funcs[func]

    ret.pack['__salt__'] = ret

    return ret


def raw_mod(opts, name, functions, mod='modules'):
    '''
    Returns a single module loaded raw and bypassing the __virtual__ function

    .. code-block:: python

        import salt.config
        import salt.loader

        __opts__ = salt.config.minion_config('/etc/salt/minion')
        testmod = salt.loader.raw_mod(__opts__, 'test', None)
        testmod['test.ping']()
    '''
    loader = LazyLoader(_module_dirs(opts, mod, 'rawmodule'),
                        opts,
                        tag='rawmodule',
                        virtual_enable=False,
                        pack={'__salt__': functions})
    # if we don't have the module, return an empty dict
    if name not in loader.file_mapping:
        return {}

    loader._load_module(name)  # load a single module (the one passed in)
    return dict(loader._dict)  # return a copy of *just* the funcs for `name`


def proxy(opts, functions, whitelist=None):
    '''
    Returns the proxy module for this salt-proxy-minion
    '''
    return LazyLoader(_module_dirs(opts, 'proxy', 'proxy'),
                         opts,
                         tag='proxy',
                         whitelist=whitelist,
                         pack={'__proxy__': functions},
                         )


def returners(opts, functions, whitelist=None):
    '''
    Returns the returner modules
    '''
    return LazyLoader(_module_dirs(opts, 'returners', 'returner'),
                      opts,
                      tag='returner',
                      whitelist=whitelist,
                      pack={'__salt__': functions})


def utils(opts, whitelist=None):
    '''
    Returns the utility modules
    '''
    return LazyLoader(_module_dirs(opts, 'utils', 'utils', ext_type_dirs='utils_dirs'),
                         opts,
                         tag='utils',
                         whitelist=whitelist,
                         )


def pillars(opts, functions):
    '''
    Returns the pillars modules
    '''
    ret = LazyLoader(_module_dirs(opts, 'pillar', 'pillar'),
                        opts,
                        tag='pillar',
                        pack={'__salt__': functions},
                        )
    return FilterDictWrapper(ret, '.ext_pillar')


def tops(opts):
    '''
    Returns the tops modules
    '''
    if 'master_tops' not in opts:
        return {}
    whitelist = opts['master_tops'].keys()
    ret = LazyLoader(_module_dirs(opts, 'tops', 'top'),
                     opts,
                     tag='top',
                     whitelist=whitelist)
    return FilterDictWrapper(ret, '.top')


def wheels(opts, whitelist=None):
    '''
    Returns the wheels modules
    '''
    return LazyLoader(_module_dirs(opts, 'wheel', 'wheel'),
                         opts,
                         tag='wheel',
                         whitelist=whitelist,
                         )


def outputters(opts):
    '''
    Returns the outputters modules
    '''
    ret = LazyLoader(_module_dirs(opts, 'output', 'output', ext_type_dirs='outputter_dirs'),
                        opts,
                        tag='output',
                        )
    wrapped_ret = FilterDictWrapper(ret, '.output')
    # TODO: this name seems terrible... __salt__ should always be execution mods
    ret.pack['__salt__'] = wrapped_ret
    return wrapped_ret


def auth(opts, whitelist=None):
    '''
    Returns the auth modules
    '''
    return LazyLoader(_module_dirs(opts, 'auth', 'auth'),
                         opts,
                         tag='auth',
                         whitelist=whitelist,
                         pack={'__salt__': minion_mods(opts)},
                         )


def fileserver(opts, backends):
    '''
    Returns the file server modules
    '''
    return LazyLoader(_module_dirs(opts, 'fileserver', 'fileserver'),
                         opts,
                         tag='fileserver',
                         whitelist=backends,
                         )


def roster(opts, whitelist=None):
    '''
    Returns the roster modules
    '''
    return LazyLoader(_module_dirs(opts, 'roster', 'roster'),
                         opts,
                         tag='roster',
                         whitelist=whitelist,
                         )


def states(opts, functions, whitelist=None):
    '''
    Returns the state modules

    .. code-block:: python

        import salt.config
        import salt.loader

        __opts__ = salt.config.minion_config('/etc/salt/minion')
        statemods = salt.loader.states(__opts__, None)
    '''
    return LazyLoader(_module_dirs(opts, 'states', 'states'),
                         opts,
                         tag='states',
                         pack={'__salt__': functions},
                         whitelist=whitelist,
                         )


def beacons(opts, functions, context=None):
    '''
    Load the beacon modules
    '''
    if context is None:
        context = {}
    return LazyLoader(_module_dirs(opts, 'beacons', 'beacons'),
                      opts,
                      tag='beacons',
                      pack={'__context__': context,
                            '__salt__': functions})


def search(opts, returners, whitelist=None):
    '''
    Returns the search modules
    '''
    return LazyLoader(_module_dirs(opts, 'search', 'search'),
                         opts,
                         tag='search',
                         whitelist=whitelist,
                         pack={'__ret__': returners},
                         )


def log_handlers(opts):
    '''
    Returns the custom logging handler modules
    '''
    ret = LazyLoader(_module_dirs(opts,
                                  'log_handlers',
                                  'log_handlers',
                                  int_type='handlers',
                                  base_path=os.path.join(SALT_BASE_PATH, 'log')),
                     opts,
                     tag='log_handlers',
                     )
    return FilterDictWrapper(ret, '.setup_handlers')


def ssh_wrapper(opts, functions=None, context=None):
    '''
    Returns the custom logging handler modules
    '''
    if context is None:
        context = {}
    if functions is None:
        functions = {}
    return LazyLoader(_module_dirs(opts,
                                   'wrapper',
                                   'wrapper',
                                   base_path=os.path.join(SALT_BASE_PATH, os.path.join('client', 'ssh'))),
                      opts,
                      tag='wrapper',
                      pack={'__salt__': functions, '__context__': context},
                      )


def render(opts, functions, states=None):
    '''
    Returns the render modules
    '''
    pack = {'__salt__': functions}
    if states:
        pack['__states__'] = states
    ret = LazyLoader(_module_dirs(opts,
                                  'renderers',
                                  'render',
                                  ext_type_dirs='render_dirs'),
                     opts,
                     tag='render',
                     pack=pack,
                     )
    rend = FilterDictWrapper(ret, '.render')

    if not check_render_pipe_str(opts['renderer'], rend):
        err = ('The renderer {0} is unavailable, this error is often because '
               'the needed software is unavailable'.format(opts['renderer']))
        log.critical(err)
        raise LoaderError(err)
    return rend


def grains(opts, force_refresh=False):
    '''
    Return the functions for the dynamic grains and the values for the static
    grains.

    .. code-block:: python

        import salt.config
        import salt.loader

        __opts__ = salt.config.minion_config('/etc/salt/minion')
        __grains__ = salt.loader.grains(__opts__)
        print __grains__['id']
    '''
    # if we hae no grains, lets try loading from disk (TODO: move to decorator?)
    if not force_refresh:
        if opts.get('grains_cache', False):
            cfn = os.path.join(
                opts['cachedir'],
                'grains.cache.p'
            )
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
    funcs = LazyLoader(_module_dirs(opts, 'grains', 'grain', ext_type_dirs='grains_dirs'),
                     opts,
                     tag='grains',
                     )
    if force_refresh:  # if we refresh, lets reload grain modules
        funcs.clear()
    # Run core grains
    for key, fun in six.iteritems(funcs):
        if not key.startswith('core.'):
            continue
        ret = fun()
        if not isinstance(ret, dict):
            continue
        grains_data.update(ret)

    # Run the rest of the grains
    for key, fun in six.iteritems(funcs):
        if key.startswith('core.') or key == '_errors':
            continue
        try:
            ret = fun()
        except Exception:
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
        grains_data.update(ret)

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

    grains_data.update(opts['grains'])
    return grains_data


# TODO: get rid of? Does anyone use this? You should use raw() instead
def call(fun, **kwargs):
    '''
    Directly call a function inside a loader directory
    '''
    args = kwargs.get('args', [])
    dirs = kwargs.get('dirs', [])

    funcs = LazyLoader([os.path.join(SALT_BASE_PATH, 'modules')] + dirs,
                          None,
                          tag='modules',
                          virtual_enable=False,
                          )
    return funcs[fun](*args)


def runner(opts):
    '''
    Directly call a function inside a loader directory
    '''
    ret = LazyLoader(_module_dirs(opts, 'runners', 'runner', ext_type_dirs='runner_dirs'),
                     opts,
                     tag='runners',
                     )
    # TODO: change from __salt__ to something else, we overload __salt__ too much
    ret.pack['__salt__'] = ret
    return ret


def queues(opts):
    '''
    Directly call a function inside a loader directory
    '''
    return LazyLoader(_module_dirs(opts, 'queues', 'queue', ext_type_dirs='queue_dirs'),
                     opts,
                     tag='queues',
                     )


def sdb(opts, functions=None, whitelist=None):
    '''
    Make a very small database call
    '''
    return LazyLoader(_module_dirs(opts, 'sdb', 'sdb'),
                     opts,
                     tag='sdb',
                     pack={'__sdb__': functions},
                     whitelist=whitelist,
                     )


def clouds(opts):
    '''
    Return the cloud functions
    '''
    # Let's bring __active_provider_name__, defaulting to None, to all cloud
    # drivers. This will get temporarily updated/overridden with a context
    # manager when needed.
    functions = LazyLoader(_module_dirs(opts,
                                           'clouds',
                                           'cloud',
                                           base_path=os.path.join(SALT_BASE_PATH, 'cloud'),
                                           int_type='clouds'),
                              opts,
                              tag='clouds',
                              pack={'__active_provider_name__': None},
                              )
    for funcname in LIBCLOUD_FUNCS_NOT_SUPPORTED:
        log.trace(
            '{0!r} has been marked as not supported. Removing from the list '
            'of supported cloud functions'.format(
                funcname
            )
        )
        functions.pop(funcname, None)
    return functions


def netapi(opts):
    '''
    Return the network api functions
    '''
    return LazyLoader(_module_dirs(opts, 'netapi', 'netapi'),
                     opts,
                     tag='netapi',
                     )


def _generate_module(name):
    if name in sys.modules:
        return

    code = "'''Salt loaded {0} parent module'''".format(name.split('.')[-1])
    module = imp.new_module(name)
    exec(code, module.__dict__)
    sys.modules[name] = module


def _mod_type(module_path):
    if module_path.startswith(SALT_BASE_PATH):
        return 'int'
    return 'ext'


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
                yield key.replace(self.suffix, '')


class LazyLoader(salt.utils.lazy.LazyDict):
    '''
    Goals here:
        - lazy loading
        - minimize disk usage

    # TODO:
        - move modules_max_memory into here
        - singletons (per tag)
    '''
    def __init__(self,
                 module_dirs,
                 opts=None,
                 tag='module',
                 loaded_base_name=None,
                 mod_type_check=None,
                 pack=None,
                 whitelist=None,
                 virtual_enable=True,
                 ):  # pylint: disable=W0231
        self.opts = self.__prep_mod_opts(opts)

        self.module_dirs = module_dirs
        if opts is None:
            opts = {}
        self.tag = tag
        self.loaded_base_name = loaded_base_name or LOADED_BASE_NAME
        self.mod_type_check = mod_type_check or _mod_type

        self.pack = {} if pack is None else pack
        if '__context__' not in self.pack:
            self.pack['__context__'] = {}

        self.whitelist = whitelist
        self.virtual_enable = virtual_enable
        self.initial_load = True

        # names of modules that we don't have (errors, __virtual__, etc.)
        self.missing_modules = {}  # mapping of name -> error
        self.loaded_modules = {}  # mapping of module_name -> dict_of_functions
        self.loaded_files = set()  # TODO: just remove them from file_mapping?

        self.disabled = set(self.opts.get('disable_{0}s'.format(self.tag), []))

        self.refresh_file_mapping()

        super(LazyLoader, self).__init__()  # late init the lazy loader
        # create all of the import namespaces
        _generate_module('{0}.int'.format(self.loaded_base_name))
        _generate_module('{0}.int.{1}'.format(self.loaded_base_name, tag))
        _generate_module('{0}.ext'.format(self.loaded_base_name))
        _generate_module('{0}.ext.{1}'.format(self.loaded_base_name, tag))

    def __getattr__(self, mod_name):
        '''
        Allow for "direct" attribute access-- this allows jinja templates to
        access things like `salt.test.ping()`
        '''
        # if we have an attribute named that, lets return it.
        try:
            return object.__getattr__(self, mod_name)
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
        mod_name = function_name.split('.')[0]
        if mod_name in self.loaded_modules:
            return '{0!r} is not available.'.format(function_name)
        else:
            if self.missing_modules.get(mod_name) is not None:
                return '\'{0}\' __virtual__ returned False: {1}'.format(mod_name, self.missing_modules[mod_name])
            elif self.missing_modules.get(mod_name) is None:
                return '\'{0}\' __virtual__ returned False'.format(mod_name)
            else:
                return '\'{0}\' is not available.'.format(function_name)

    def refresh_file_mapping(self):
        '''
        refresh the mapping of the FS on disk
        '''
        # map of suffix to description for imp
        self.suffix_map = {}
        suffix_order = []  # local list to determine precedence of extensions
        for (suffix, mode, kind) in imp.get_suffixes():
            self.suffix_map[suffix] = (suffix, mode, kind)
            suffix_order.append(suffix)

        if self.opts.get('cython_enable', True) is True:
            try:
                self.pyximport = __import__('pyximport')  # pylint: disable=import-error
                self.pyximport.install()
                # add to suffix_map so file_mapping will pick it up
                self.suffix_map['.pyx'] = tuple()
            except ImportError:
                log.info('Cython is enabled in the options but not present '
                    'in the system path. Skipping Cython modules.')
        # allow for module dirs
        self.suffix_map[''] = ('', '', imp.PKG_DIRECTORY)

        # create mapping of filename (without suffix) to (path, suffix)
        self.file_mapping = {}

        for mod_dir in self.module_dirs:
            files = []
            try:
                files = os.listdir(mod_dir)
            except OSError:
                continue
            for filename in files:
                try:
                    if filename.startswith('_'):
                        # skip private modules
                        # log messages omitted for obviousness
                        continue
                    f_noext, ext = os.path.splitext(filename)
                    # make sure it is a suffix we support
                    if ext not in self.suffix_map:
                        continue
                    if f_noext in self.disabled:
                        log.trace(
                            'Skipping {0}, it is disabled by configuration'.format(
                            filename
                            )
                        )
                        continue
                    fpath = os.path.join(mod_dir, filename)
                    # if its a directory, lets allow us to load that
                    if ext == '':
                        # is there something __init__?
                        subfiles = os.listdir(fpath)
                        sub_path = None
                        for suffix in suffix_order:
                            init_file = '__init__{0}'.format(suffix)
                            if init_file in subfiles:
                                sub_path = os.path.join(fpath, init_file)
                                break
                        if sub_path is not None:
                            self.file_mapping[f_noext] = (fpath, ext)

                    # if we don't have it, we want it
                    elif f_noext not in self.file_mapping:
                        self.file_mapping[f_noext] = (fpath, ext)
                    # if we do, we want it if we have a higher precidence ext
                    else:
                        curr_ext = self.file_mapping[f_noext][1]
                        if suffix_order.index(ext) < suffix_order.index(curr_ext):
                            self.file_mapping[f_noext] = (fpath, ext)
                except OSError:
                    continue

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
        if hasattr(self, 'opts'):
            self.refresh_file_mapping()
        self.initial_load = False

    def __prep_mod_opts(self, opts):
        '''
        Strip out of the opts any logger instance
        '''
        if 'grains' in opts:
            self._grains = opts['grains']
        else:
            self._grains = {}
        if 'pillar' in opts:
            self._pillar = opts['pillar']
        else:
            self._pillar = {}

        mod_opts = {}
        for key, val in opts.items():
            if key in ('logger', 'grains'):
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
            if submodule.__name__.startswith(mod.__name__ + '.'):
                reload(submodule)
                self._reload_submodules(submodule)

    def _load_module(self, name):
        mod = None
        fpath, suffix = self.file_mapping[name]
        self.loaded_files.add(name)
        try:
            sys.path.append(os.path.dirname(fpath))
            if suffix == '.pyx':
                mod = self.pyximport.load_module(name, fpath, tempfile.gettempdir())
            else:
                desc = self.suffix_map[suffix]
                # if it is a directory, we dont open a file
                if suffix == '':
                    mod = imp.load_module(
                        '{0}.{1}.{2}.{3}'.format(
                            self.loaded_base_name,
                            self.mod_type_check(fpath),
                            self.tag,
                            name
                        ), None, fpath, desc)
                    # reload all submodules if necessary
                    if not self.initial_load:
                        self._reload_submodules(mod)
                else:
                    with open(fpath, desc[1]) as fn_:
                        mod = imp.load_module(
                            '{0}.{1}.{2}.{3}'.format(
                                self.loaded_base_name,
                                self.mod_type_check(fpath),
                                self.tag,
                                name
                            ), fn_, fpath, desc)

        except IOError:
            raise
        except ImportError:
            log.debug(
                'Failed to import {0} {1}:\n'.format(
                    self.tag, name
                ),
                exc_info=True
            )
            return mod
        except Exception:
            log.error(
                'Failed to import {0} {1}, this is due most likely to a '
                'syntax error:\n'.format(
                    self.tag, name
                ),
                exc_info=True
            )
            return mod
        except SystemExit:
            log.error(
                'Failed to import {0} {1} as the module called exit()\n'.format(
                    self.tag, name
                ),
                exc_info=True
            )
            return mod
        finally:
            sys.path.pop()

        if hasattr(mod, '__opts__'):
            mod.__opts__.update(self.opts)
        else:
            mod.__opts__ = self.opts

        mod.__grains__ = self._grains
        mod.__pillar__ = self._pillar

        # pack whatever other globals we were asked to
        for p_name, p_value in six.iteritems(self.pack):
            setattr(mod, p_name, p_value)

        # Call a module's initialization method if it exists
        module_init = getattr(mod, '__init__', None)
        if inspect.isfunction(module_init):
            try:
                module_init(self.opts)
            except TypeError:
                pass
        module_name = mod.__name__.rsplit('.', 1)[-1]

        # if virtual modules are enabled, we need to look for the
        # __virtual__() function inside that module and run it.
        if self.virtual_enable:
            (virtual_ret, module_name, virtual_err) = self.process_virtual(
                mod,
                module_name,
            )
            if virtual_err is not None:
                log.debug('Error loading {0}.{1}: {2}'.format(self.tag,
                                                              module_name,
                                                              virtual_err,
                                                              ))

            # if process_virtual returned a non-True value then we are
            # supposed to not process this module
            if virtual_ret is not True:
                # If a module has information about why it could not be loaded, record it
                self.missing_modules[module_name] = virtual_err
                self.missing_modules[name] = virtual_err
                return False

        # If this is a proxy minion then MOST modules cannot work. Therefore, require that
        # any module that does work with salt-proxy-minion define __proxyenabled__ as a list
        # containing the names of the proxy types that the module supports.
        if not hasattr(mod, 'render') and 'proxy' in self.opts:
            if not hasattr(mod, '__proxyenabled__') or \
                    self.opts['proxy']['proxytype'] in mod.__proxyenabled__ or \
                    '*' in mod.__proxyenabled__:
                err_string = 'not a proxy_minion enabled module'
                self.missing_modules[module_name] = err_string
                self.missing_modules[name] = err_string
                return False

        if getattr(mod, '__load__', False) is not False:
            log.info(
                'The functions from module {0!r} are being loaded from the '
                'provided __load__ attribute'.format(
                    module_name
                )
            )
        mod_dict = salt.utils.odict.OrderedDict()
        for attr in getattr(mod, '__load__', dir(mod)):
            if attr.startswith('_'):
                # private functions are skipped
                continue
            func = getattr(mod, attr)
            if not inspect.isfunction(func):
                # Not a function!? Skip it!!!
                continue
            # Let's get the function name.
            # If the module has the __func_alias__ attribute, it must be a
            # dictionary mapping in the form of(key -> value):
            #   <real-func-name> -> <desired-func-name>
            #
            # It default's of course to the found callable attribute name
            # if no alias is defined.
            funcname = getattr(mod, '__func_alias__', {}).get(attr, attr)
            # Save many references for lookups
            self._dict['{0}.{1}'.format(module_name, funcname)] = func
            setattr(mod_dict, funcname, func)
            mod_dict[funcname] = func
            self._apply_outputter(func, mod)

        # enforce depends
        try:
            Depends.enforce_dependencies(self._dict, self.tag)
        except RuntimeError as e:
            log.info('Depends.enforce_dependencies() failed '
                     'for reasons: {0}'.format(e))

        self.loaded_modules[module_name] = mod_dict
        return True

    def _load(self, key):
        '''
        Load a single item if you have it
        '''
        # if the key doesn't have a '.' then it isn't valid for this mod dict
        if not isinstance(key, six.string_types) or '.' not in key:
            raise KeyError
        mod_name, _ = key.split('.', 1)
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

    def _apply_outputter(self, func, mod):
        '''
        Apply the __outputter__ variable to the functions
        '''
        if hasattr(mod, '__outputter__'):
            outp = mod.__outputter__
            if func.__name__ in outp:
                func.__outputter__ = outp[func.__name__]

    def process_virtual(self, mod, module_name):
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
        try:
            error_reason = None
            if hasattr(mod, '__virtual__') and inspect.isfunction(mod.__virtual__):
                if self.opts.get('virtual_timer', False):
                    start = time.time()
                    virtual = mod.__virtual__()
                    if isinstance(virtual, tuple):
                        error_reason = virtual[1]
                        virtual = virtual[0]
                    end = time.time() - start
                    msg = 'Virtual function took {0} seconds for {1}'.format(
                            end, module_name)
                    log.warning(msg)
                else:
                    try:
                        virtual = mod.__virtual__()
                        if isinstance(virtual, tuple):
                            error_reason = virtual[1]
                            virtual = virtual[0]
                    except Exception as exc:
                        log.error('Exception raised when processing __virtual__ function'
                                  ' for {0}. Module will not be loaded {1}'.format(
                                      module_name, exc))
                        virtual = None
                # Get the module's virtual name
                virtualname = getattr(mod, '__virtualname__', virtual)
                if not virtual:
                    # if __virtual__() evaluates to False then the module
                    # wasn't meant for this platform or it's not supposed to
                    # load for some other reason.

                    # Some modules might accidentally return None and are
                    # improperly loaded
                    if virtual is None:
                        log.warning(
                            '{0}.__virtual__() is wrongly returning `None`. '
                            'It should either return `True`, `False` or a new '
                            'name. If you\'re the developer of the module '
                            '{1!r}, please fix this.'.format(
                                mod.__name__,
                                module_name
                            )
                        )

                    return (False, module_name, error_reason)

                # At this point, __virtual__ did not return a
                # boolean value, let's check for deprecated usage
                # or module renames
                if virtual is not True and module_name != virtual:
                    # The module is renaming itself. Updating the module name
                    # with the new name
                    log.trace('Loaded {0} as virtual {1}'.format(
                        module_name, virtual
                    ))

                    if not hasattr(mod, '__virtualname__'):
                        salt.utils.warn_until(
                            'Hydrogen',
                            'The {0!r} module is renaming itself in it\'s '
                            '__virtual__() function ({1} => {2}). Please '
                            'set it\'s virtual name as the '
                            '\'__virtualname__\' module attribute. '
                            'Example: "__virtualname__ = {2!r}"'.format(
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
                            'The module {0!r} is showing some bad usage. It\'s '
                            '__virtualname__ attribute is set to {1!r} yet the '
                            '__virtual__() function is returning {2!r}. These '
                            'values should match!'.format(
                                mod.__name__,
                                virtualname,
                                virtual
                            )
                        )

                    module_name = virtualname

                # If the __virtual__ function returns True and __virtualname__ is set then use it
                elif virtual is True and virtualname != module_name:
                    if virtualname is not True:
                        module_name = virtualname

        except KeyError:
            # Key errors come out of the virtual function when passing
            # in incomplete grains sets, these can be safely ignored
            # and logged to debug, still, it includes the traceback to
            # help debugging.
            log.debug(
                'KeyError when loading {0}'.format(module_name),
                exc_info=True
            )

        except Exception:
            # If the module throws an exception during __virtual__()
            # then log the information and continue to the next.
            log.error(
                'Failed to read the virtual function for '
                '{0}: {1}'.format(
                    self.tag, module_name
                ),
                exc_info=True
            )
            return (False, module_name, error_reason)

        return (True, module_name, None)
