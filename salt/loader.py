# -*- coding: utf-8 -*-
'''
Routines to set up a minion
'''

# Import python libs
import os
import imp
import sys
import salt
import logging
import tempfile
import time

from collections import MutableMapping

# Import salt libs
from salt.exceptions import LoaderError
from salt.template import check_render_pipe_str
from salt.utils.decorators import Depends
from salt.utils.odict import OrderedDict

# Solve the Chicken and egg problem where grains need to run before any
# of the modules are loaded and are generally available for any usage.
import salt.modules.cmdmod

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


def _create_loader(
        opts,
        ext_type,
        tag,
        int_type=None,
        ext_dirs=True,
        ext_type_dirs=None,
        base_path=None,
        loaded_base_name=None,
        mod_type_check=None):
    '''
    Creates Loader instance

    Order of module_dirs:
        cli flag -m MODULE_DIRS
        opts[ext_type_dirs],
        extension types,
        base types.
    '''
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

    if loaded_base_name is None:
        loaded_base_name = LOADED_BASE_NAME

    if mod_type_check is None:
        mod_type_check = _mod_type

    module_dirs = cli_module_dirs + ext_type_types + [ext_types, sys_types]
    _generate_module('{0}.int'.format(loaded_base_name))
    _generate_module('{0}.int.{1}'.format(loaded_base_name, tag))
    _generate_module('{0}.ext'.format(loaded_base_name))
    _generate_module('{0}.ext.{1}'.format(loaded_base_name, tag))
    return Loader(
        module_dirs,
        opts,
        tag,
        loaded_base_name=loaded_base_name,
        mod_type_check=mod_type_check
    )


def minion_mods(opts, context=None, whitelist=None):
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
    load = _create_loader(opts, 'modules', 'module')
    if context is None:
        context = {}
    pack = {'name': '__context__',
            'value': context}
    if not whitelist:
        whitelist = opts.get('whitelist_modules', None)
    functions = load.gen_functions(
        pack,
        whitelist=whitelist,
        provider_overrides=True
    )
    # Enforce dependencies of module functions from "functions"
    Depends.enforce_dependencies(functions)
    return functions


def raw_mod(opts, name, functions):
    '''
    Returns a single module loaded raw and bypassing the __virtual__ function

    .. code-block:: python

        import salt.config
        import salt.loader

        __opts__ = salt.config.minion_config('/etc/salt/minion')
        testmod = salt.loader.raw_mod(__opts__, 'test', None)
        testmod['test.ping']()
    '''
    load = _create_loader(opts, 'modules', 'rawmodule')
    return load.gen_module(name, functions)


def proxy(opts, functions, whitelist=None):
    '''
    Returns the proxy module for this salt-proxy-minion
    '''
    load = _create_loader(opts, 'proxy', 'proxy')
    pack = {'name': '__proxy__',
            'value': functions}
    return load.gen_functions(pack, whitelist=whitelist)


def returners(opts, functions, whitelist=None):
    '''
    Returns the returner modules
    '''
    load = _create_loader(opts, 'returners', 'returner')
    pack = {'name': '__salt__',
            'value': functions}
    return LazyLoader(load,
                      functions,
                      pack,
                      whitelist=whitelist,
                      )


def pillars(opts, functions):
    '''
    Returns the pillars modules
    '''
    load = _create_loader(opts, 'pillar', 'pillar')
    pack = {'name': '__salt__',
            'value': functions}
    return load.filter_func('ext_pillar', pack)


def tops(opts):
    '''
    Returns the tops modules
    '''
    if 'master_tops' not in opts:
        return {}
    whitelist = opts['master_tops'].keys()
    load = _create_loader(opts, 'tops', 'top')
    topmodules = load.filter_func('top', whitelist=whitelist)
    return topmodules


def wheels(opts, whitelist=None):
    '''
    Returns the wheels modules
    '''
    load = _create_loader(opts, 'wheel', 'wheel')
    return load.gen_functions(whitelist=whitelist)


def outputters(opts):
    '''
    Returns the outputters modules
    '''
    load = _create_loader(
        opts,
        'output',
        'output',
        ext_type_dirs='outputter_dirs')
    return load.filter_func('output')


def auth(opts, whitelist=None):
    '''
    Returns the auth modules
    '''
    load = _create_loader(opts, 'auth', 'auth')
    return load.gen_functions(whitelist=whitelist)


def fileserver(opts, backends):
    '''
    Returns the file server modules
    '''
    load = _create_loader(opts, 'fileserver', 'fileserver')
    return load.gen_functions(whitelist=backends)


def roster(opts, whitelist=None):
    '''
    Returns the roster modules
    '''
    load = _create_loader(opts, 'roster', 'roster')
    return load.gen_functions(whitelist=whitelist)


def states(opts, functions, whitelist=None):
    '''
    Returns the state modules

    .. code-block:: python

        import salt.config
        import salt.loader

        __opts__ salt.config.minion_config('/etc/salt/minion')
        statemods = salt.loader.states(__opts__, None)
    '''
    load = _create_loader(opts, 'states', 'states')
    pack = {'name': '__salt__',
            'value': functions}
    return load.gen_functions(pack, whitelist=whitelist)


def search(opts, returners, whitelist=None):
    '''
    Returns the search modules
    '''
    load = _create_loader(opts, 'search', 'search')
    pack = {'name': '__ret__',
            'value': returners}
    return LazyLoader(load, pack=pack, whitelist=whitelist)


def log_handlers(opts):
    '''
    Returns the custom logging handler modules
    '''
    load = _create_loader(
        opts,
        'log_handlers',
        'log_handlers',
        int_type='handlers',
        base_path=os.path.join(SALT_BASE_PATH, 'log')
    )
    return load.filter_func('setup_handlers')


def ssh_wrapper(opts, functions=None, context=None):
    '''
    Returns the custom logging handler modules
    '''
    if context is None:
        context = {}
    if functions is None:
        functions = {}
    load = _create_loader(
        opts,
        'wrapper',
        'wrapper',
        base_path=os.path.join(SALT_BASE_PATH, os.path.join(
            'client',
            'ssh'))
    )
    pack = [{'name': '__salt__',
             'value': functions},
            {'name': '__context__',
             'value': context}]
    return load.gen_functions(pack)


def render(opts, functions, states=None):
    '''
    Returns the render modules
    '''
    load = _create_loader(
        opts, 'renderers', 'render', ext_type_dirs='render_dirs'
    )
    pack = [{'name': '__salt__',
             'value': functions},
            {'name': '__pillar__',
             'value': opts.get('pillar', {})}]

    if states:
        pack.append({'name': '__states__', 'value': states})
    rend = load.filter_func('render', pack)
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

        __opts__ salt.config.minion_config('/etc/salt/minion')
        __grains__ = salt.loader.grains(__opts__)
        print __grains__['id']
    '''
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
    load = _create_loader(opts, 'grains', 'grain', ext_type_dirs='grains_dirs')
    grains_info = load.gen_grains(force_refresh)
    grains_info.update(opts['grains'])
    return grains_info


def call(fun, **kwargs):
    '''
    Directly call a function inside a loader directory
    '''
    args = kwargs.get('args', [])
    dirs = kwargs.get('dirs', [])
    module_dirs = [os.path.join(SALT_BASE_PATH, 'modules')] + dirs
    load = Loader(module_dirs)
    return load.call(fun, args)


def runner(opts):
    '''
    Directly call a function inside a loader directory
    '''
    load = _create_loader(
        opts, 'runners', 'runner', ext_type_dirs='runner_dirs'
    )
    return load.gen_functions()


def queues(opts):
    '''
    Directly call a function inside a loader directory
    '''
    load = _create_loader(
        opts, 'queues', 'queue', ext_type_dirs='queue_dirs'
    )
    return load.gen_functions()


def sdb(opts, functions=None, whitelist=None):
    '''
    Make a very small database call
    '''
    load = _create_loader(opts, 'sdb', 'sdb')
    pack = {'name': '__sdb__',
            'value': functions}
    return LazyLoader(load,
                      functions,
                      pack,
                      whitelist=whitelist,
                      )


def clouds(opts):
    '''
    Return the cloud functions
    '''
    load = _create_loader(opts,
                          'clouds',
                          'cloud',
                          base_path=os.path.join(SALT_BASE_PATH, 'cloud'),
                          int_type='clouds')

    # Let's bring __active_provider_name__, defaulting to None, to all cloud
    # drivers. This will get temporarily updated/overridden with a context
    # manager when needed.
    pack = {
        'name': '__active_provider_name__',
        'value': None
    }

    functions = load.gen_functions(pack)
    for funcname in LIBCLOUD_FUNCS_NOT_SUPPORTED:
        log.debug(
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
    load = salt.loader._create_loader(opts, 'netapi', 'netapi')
    return load.gen_functions()


def _generate_module(name):
    if name in sys.modules:
        return

    code = "'''Salt loaded {0} parent module'''".format(name.split('.')[-1])
    module = imp.new_module(name)
    exec code in module.__dict__
    sys.modules[name] = module


def _mod_type(module_path):
    if module_path.startswith(SALT_BASE_PATH):
        return 'int'
    return 'ext'


def in_pack(pack, name):
    '''
    Returns if the passed name is in the pack
    '''
    if isinstance(pack, list):
        for chunk in pack:
            if not isinstance(chunk, dict):
                continue
            try:
                if name == chunk['name']:
                    return True
            except KeyError:
                pass
    elif isinstance(pack, dict):
        try:
            if name == pack['name']:
                return True
        except KeyError:
            pass
    return False


class Loader(object):
    '''
    Used to load in arbitrary modules from a directory, the Loader can
    also be used to only load specific functions from a directory, or to
    call modules in an arbitrary directory directly.
    '''
    def __init__(self,
                 module_dirs,
                 opts=None,
                 tag='module',
                 loaded_base_name=None,
                 mod_type_check=None):
        self.module_dirs = module_dirs
        if opts is None:
            opts = {}
        self.tag = tag
        if 'grains' in opts:
            self.grains = opts['grains']
        else:
            self.grains = {}
        if 'pillar' in opts:
            self.pillar = opts['pillar']
        else:
            self.pillar = {}
        self.opts = self.__prep_mod_opts(opts)
        self.loaded_base_name = loaded_base_name or LOADED_BASE_NAME
        self.mod_type_check = mod_type_check or _mod_type
        if self.opts.get('grains_cache', False):
            self.serial = salt.payload.Serial(self.opts)

    def __prep_mod_opts(self, opts):
        '''
        Strip out of the opts any logger instance
        '''
        mod_opts = {}
        for key, val in opts.items():
            if key in ('logger', 'grains'):
                continue
            mod_opts[key] = val
        return mod_opts

    def call(self, fun, arg=None):
        '''
        Call a function in the load path.
        '''
        if arg is None:
            arg = []
        name = fun[:fun.rindex('.')]
        try:
            fn_, path, desc = imp.find_module(name, self.module_dirs)
            mod = imp.load_module(name, fn_, path, desc)
        except ImportError:
            if self.opts.get('cython_enable', True) is True:
                # The module was not found, try to find a cython module
                try:
                    import pyximport  # pylint: disable=import-error
                    pyximport.install()

                    for mod_dir in self.module_dirs:
                        for fn_ in os.listdir(mod_dir):
                            if name == fn_[:fn_.rindex('.')]:
                                # Found it, load the mod and break the loop
                                mod = pyximport.load_module(
                                    name, os.path.join(mod_dir, fn_)
                                )
                                return getattr(
                                    mod, fun[fun.rindex('.') + 1:])(*arg)
                except ImportError:
                    log.info('Cython is enabled in options though it\'s not '
                             'present in the system path. Skipping Cython '
                             'modules.')
        return getattr(mod, fun[fun.rindex('.') + 1:])(*arg)

    def gen_module(self, name, functions, pack=None):
        '''
        Load a single module and pack it with the functions passed
        '''
        full = ''
        mod = None
        for mod_dir in self.module_dirs:
            if not os.path.isabs(mod_dir):
                continue
            if not os.path.isdir(mod_dir):
                continue
            fn_ = os.path.join(mod_dir, name)
            if os.path.isdir(fn_):
                full = fn_
                break
            else:
                for ext in ('.py', '.pyo', '.pyc', '.so'):
                    full_test = '{0}{1}'.format(fn_, ext)
                    if os.path.isfile(full_test):
                        full = full_test
                        break
                if full:
                    break
        if not full:
            return None

        cython_enabled = False
        if self.opts.get('cython_enable', True) is True:
            try:
                import pyximport  # pylint: disable=import-error
                pyximport.install()
                cython_enabled = True
            except ImportError:
                log.info('Cython is enabled in the options but not present '
                         'in the system path. Skipping Cython modules.')
        try:
            if full.endswith('.pyx') and cython_enabled:
                # If there's a name which ends in .pyx it means the above
                # cython_enabled is True. Continue...
                mod = pyximport.load_module(name, full, tempfile.gettempdir())
            else:
                fn_, path, desc = imp.find_module(name, self.module_dirs)
                mod = imp.load_module(
                    '{0}.{1}.{2}.{3}'.format(
                        self.loaded_base_name,
                        self.mod_type_check(path),
                        self.tag,
                        name
                    ), fn_, path, desc
                )
        except ImportError:
            log.debug(
                'Failed to import {0} {1}:\n'.format(
                    self.tag, name
                ),
                exc_info=True
            )
            return mod
        except Exception:
            log.warning(
                'Failed to import {0} {1}, this is due most likely to a '
                'syntax error:\n'.format(
                    self.tag, name
                ),
                exc_info=True
            )
            return mod
        if hasattr(mod, '__opts__'):
            mod.__opts__.update(self.opts)
        else:
            mod.__opts__ = self.opts

        mod.__grains__ = self.grains

        if pack:
            if isinstance(pack, list):
                for chunk in pack:
                    try:
                        setattr(mod, chunk['name'], chunk['value'])
                    except KeyError:
                        pass
            else:
                setattr(mod, pack['name'], pack['value'])

        # Call a module's initialization method if it exists
        if hasattr(mod, '__init__'):
            if callable(mod.__init__):
                try:
                    mod.__init__(self.opts)
                except TypeError:
                    pass
        funcs = {}
        module_name = mod.__name__[mod.__name__.rindex('.') + 1:]
        if getattr(mod, '__load__', False) is not False:
            log.info(
                'The functions from module {0!r} are being loaded from the '
                'provided __load__ attribute'.format(
                    module_name
                )
            )
        for attr in getattr(mod, '__load__', dir(mod)):
            if attr.startswith('_'):
                # private functions are skipped
                continue
            if callable(getattr(mod, attr)):
                func = getattr(mod, attr)
                if hasattr(func, '__bases__'):
                    if 'BaseException' in func.__bases__:
                        # the callable object is an exception, don't load it
                        continue

                # Let's get the function name.
                # If the module has the __func_alias__ attribute, it must be a
                # dictionary mapping in the form of(key -> value):
                #   <real-func-name> -> <desired-func-name>
                #
                # It default's of course to the found callable attribute name
                # if no alias is defined.
                funcname = getattr(mod, '__func_alias__', {}).get(attr, attr)
                funcs['{0}.{1}'.format(module_name, funcname)] = func
                self._apply_outputter(func, mod)
        if not hasattr(mod, '__salt__'):
            mod.__salt__ = functions
        try:
            context = sys.modules[
                functions[functions.iterkeys().next()].__module__
            ].__context__
        except (AttributeError, StopIteration):
            context = {}
        mod.__context__ = context
        return funcs

    def gen_functions(self, pack=None, virtual_enable=True, whitelist=None,
                      provider_overrides=False):
        '''
        Return a dict of functions found in the defined module_dirs
        '''
        funcs = OrderedDict()
        self.load_modules()
        for mod in self.modules:
            # If this is a proxy minion then MOST modules cannot work.  Therefore, require that
            # any module that does work with salt-proxy-minion define __proxyenabled__ as a list
            # containing the names of the proxy types that the module supports.
            if not hasattr(mod, 'render') and 'proxy' in self.opts:
                if not hasattr(mod, '__proxyenabled__'):
                    # This is a proxy minion but this module doesn't support proxy
                    # minions at all
                    continue
                if not (self.opts['proxy']['proxytype'] in mod.__proxyenabled__ or
                        '*' in mod.__proxyenabled__):
                    # This is a proxy minion, this module supports proxy
                    # minions, but not this particular minion
                    log.debug(mod)
                    continue

            if hasattr(mod, '__opts__'):
                mod.__opts__.update(self.opts)
            else:
                mod.__opts__ = self.opts

            mod.__grains__ = self.grains
            mod.__pillar__ = self.pillar

            if pack:
                if isinstance(pack, list):
                    for chunk in pack:
                        if not isinstance(chunk, dict):
                            continue
                        try:
                            setattr(mod, chunk['name'], chunk['value'])
                        except KeyError:
                            pass
                else:
                    setattr(mod, pack['name'], pack['value'])

            # Call a module's initialization method if it exists
            if hasattr(mod, '__init__'):
                if callable(mod.__init__):
                    try:
                        mod.__init__(self.opts)
                    except TypeError:
                        pass

            # Trim the full pathname to just the module
            # this will be the short name that other salt modules and state
            # will refer to it as.
            module_name = mod.__name__.rsplit('.', 1)[-1]

            if virtual_enable:
                # if virtual modules are enabled, we need to look for the
                # __virtual__() function inside that module and run it.
                (virtual_ret, virtual_name) = self.process_virtual(mod,
                                                                   module_name)

                # if process_virtual returned a non-True value then we are
                # supposed to not process this module
                if virtual_ret is not True:
                    continue

                # update our module name to reflect the virtual name
                module_name = virtual_name

            if whitelist:
                # If a whitelist is defined then only load the module if it is
                # in the whitelist
                if module_name not in whitelist:
                    continue

            # load the functions from the module and update our dict
            funcs.update(self.load_functions(mod, module_name))

        # Handle provider overrides
        if provider_overrides and self.opts.get('providers', False):
            if isinstance(self.opts['providers'], dict):
                for mod, provider in self.opts['providers'].items():
                    newfuncs = raw_mod(self.opts, provider, funcs)
                    if newfuncs:
                        for newfunc in newfuncs:
                            f_key = '{0}{1}'.format(
                                mod, newfunc[newfunc.rindex('.'):]
                            )
                            funcs[f_key] = newfuncs[newfunc]

        # now that all the functions have been collected, iterate back over
        # the available modules and inject the special __salt__ namespace that
        # contains these functions.
        for mod in self.modules:
            if not hasattr(mod, '__salt__') or (
                not in_pack(pack, '__salt__') and
                (not str(mod.__name__).startswith('salt.loaded.int.grain') and
                 not str(mod.__name__).startswith('salt.loaded.ext.grain'))
            ):
                mod.__salt__ = funcs
            elif not in_pack(pack, '__salt__') and \
                    (str(mod.__name__).startswith('salt.loaded.int.grain') or
                     str(mod.__name__).startswith('salt.loaded.ext.grain')):
                mod.__salt__.update(funcs)
        return funcs

    def load_modules(self):
        '''
        Loads all of the modules from module_dirs and returns a list of them
        '''

        self.modules = []

        log.trace('loading {0} in {1}'.format(self.tag, self.module_dirs))
        names = OrderedDict()
        disable = set(self.opts.get('disable_{0}s'.format(self.tag), []))

        cython_enabled = False
        if self.opts.get('cython_enable', True) is True:
            try:
                import pyximport  # pylint: disable=import-error
                pyximport.install()
                cython_enabled = True
            except ImportError:
                log.info('Cython is enabled in the options but not present '
                         'in the system path. Skipping Cython modules.')
        for mod_dir in self.module_dirs:
            if not os.path.isabs(mod_dir):
                log.trace(
                    'Skipping {0}, it is not an absolute path'.format(
                        mod_dir
                    )
                )
                continue
            if not os.path.isdir(mod_dir):
                log.trace(
                    'Skipping {0}, it is not a directory'.format(
                        mod_dir
                    )
                )
                continue
            for fn_ in os.listdir(mod_dir):
                if fn_.startswith('_'):
                    # skip private modules
                    # log messages omitted for obviousness
                    continue
                if fn_.split('.')[0] in disable:
                    log.trace(
                        'Skipping {0}, it is disabled by configuration'.format(
                            fn_
                        )
                    )
                    continue

                if fn_.endswith(('.pyc', '.pyo')):
                    non_compiled_filename = '{0}.py'.format(os.path.splitext(fn_)[0])
                    if os.path.exists(os.path.join(mod_dir, non_compiled_filename)):
                        # Let's just process the non compiled python modules
                        continue

                if (fn_.endswith(('.py', '.pyc', '.pyo', '.so'))
                        or (cython_enabled and fn_.endswith('.pyx'))
                        or os.path.isdir(os.path.join(mod_dir, fn_))):

                    extpos = fn_.rfind('.')
                    if extpos > 0:
                        _name = fn_[:extpos]
                    else:
                        _name = fn_

                    if _name in names:
                        # Since we load custom modules first, if this logic is true it means
                        # that an internal module was shadowed by an external custom module
                        log.trace(
                            'The {0!r} module from {1!r} was shadowed by '
                            'the module in {2!r}'.format(
                                _name,
                                mod_dir,
                                names[_name],
                            )
                        )
                        continue

                    names[_name] = os.path.join(mod_dir, fn_)
                else:
                    log.trace(
                        'Skipping {0}, it does not end with an expected '
                        'extension'.format(
                            fn_
                        )
                    )
        for name in names:
            try:
                if names[name].endswith('.pyx'):
                    # If there's a name which ends in .pyx it means the above
                    # cython_enabled is True. Continue...
                    mod = pyximport.load_module(
                        '{0}.{1}.{2}.{3}'.format(
                            self.loaded_base_name,
                            self.mod_type_check(names[name]),
                            self.tag,
                            name
                        ), names[name], tempfile.gettempdir()
                    )
                else:
                    fn_, path, desc = imp.find_module(name, self.module_dirs)
                    mod = imp.load_module(
                        '{0}.{1}.{2}.{3}'.format(
                            self.loaded_base_name,
                            self.mod_type_check(path),
                            self.tag,
                            name
                        ), fn_, path, desc
                    )
                    # reload all submodules if necessary
                    submodules = [
                        getattr(mod, sname) for sname in dir(mod) if
                        isinstance(getattr(mod, sname), mod.__class__)
                    ]

                    # reload only custom "sub"modules i.e is a submodule in
                    # parent module that are still available on disk (i.e. not
                    # removed during sync_modules)
                    for submodule in submodules:
                        try:
                            smname = '{0}.{1}.{2}'.format(
                                self.loaded_base_name,
                                self.tag,
                                name
                            )
                            smfile = '{0}.py'.format(
                                os.path.splitext(submodule.__file__)[0]
                            )
                            if submodule.__name__.startswith(smname) and \
                                    os.path.isfile(smfile):
                                reload(submodule)
                        except AttributeError:
                            continue
            except ImportError:
                log.debug(
                    'Failed to import {0} {1}, this is most likely NOT a '
                    'problem:\n'.format(
                        self.tag, name
                    ),
                    exc_info=True
                )
                continue
            except Exception:
                log.warning(
                    'Failed to import {0} {1}, this is due most likely to a '
                    'syntax error. Traceback raised:\n'.format(
                        self.tag, name
                    ),
                    exc_info=True
                )
                continue
            self.modules.append(mod)

    def load_functions(self, mod, module_name):
        '''
        Load functions returns a dict of all the functions from a module
        '''
        funcs = {}

        if getattr(mod, '__load__', False) is not False:
            log.info(
                'The functions from module {0!r} are being loaded from '
                'the provided __load__ attribute'.format(
                    module_name
                )
            )

        for attr in getattr(mod, '__load__', dir(mod)):
            if attr.startswith('_'):
                # skip private attributes
                # log messages omitted for obviousness
                continue

            if callable(getattr(mod, attr)):
                # check to make sure this is callable
                func = getattr(mod, attr)
                if isinstance(func, type):
                    # skip callables that might be exceptions
                    if any(['Error' in func.__name__,
                            'Exception' in func.__name__]):
                        continue

                # now that callable passes all the checks, add it to the
                # library of available functions of this type

                # Let's get the function name.
                # If the module has the __func_alias__ attribute, it must
                # be a dictionary mapping in the form of(key -> value):
                #   <real-func-name> -> <desired-func-name>
                #
                # It default's of course to the found callable attribute
                # name if no alias is defined.
                funcname = getattr(mod, '__func_alias__', {}).get(
                    attr, attr
                )

                # functions are namespaced with their module name, unless
                # the module_name is None (this is a special case added for
                # pyobjects), in which case just the function name is used
                if module_name is None:
                    module_func_name = funcname
                else:
                    module_func_name = '{0}.{1}'.format(module_name, funcname)

                funcs[module_func_name] = func
                log.trace(
                    'Added {0} to {1}'.format(module_func_name, self.tag)
                )
                self._apply_outputter(func, mod)
        return funcs

    def process_virtual(self, mod, module_name):
        '''
        Given a loaded module and its default name determine its virtual name

        This function returns a tuple. The first value will be either True or
        False and will indicate if the module should be loaded or not (ie. if
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
            if hasattr(mod, '__virtual__') and callable(mod.__virtual__):
                if self.opts.get('virtual_timer', False):
                    start = time.time()
                    virtual = mod.__virtual__()
                    end = time.time() - start
                    msg = 'Virtual function took {0} seconds for {1}'.format(
                            end, module_name)
                    log.warning(msg)
                else:
                    virtual = mod.__virtual__()
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

                    return (False, module_name)

                # At this point, __virtual__ did not return a
                # boolean value, let's check for deprecated usage
                # or module renames
                if virtual is not True and module_name == virtual:
                    # The module was not renamed, it should
                    # have returned True instead
                    #salt.utils.warn_until(
                    #    'Helium',
                    #    'The {0!r} module is NOT renaming itself and is '
                    #    'returning a string. In this case the __virtual__() '
                    #    'function should simply return `True`. This usage will '
                    #    'become an error in Salt Helium'.format(
                    #        mod.__name__,
                    #    )
                    #)
                    pass

                elif virtual is not True and module_name != virtual:
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
            return (False, module_name)

        return (True, module_name)

    def _apply_outputter(self, func, mod):
        '''
        Apply the __outputter__ variable to the functions
        '''
        if hasattr(mod, '__outputter__'):
            outp = mod.__outputter__
            if func.__name__ in outp:
                func.__outputter__ = outp[func.__name__]

    def filter_func(self, name, pack=None, whitelist=None):
        '''
        Filter a specific function out of the functions, this is used to load
        the returners for the salt minion
        '''
        funcs = {}
        gen = self.gen_functions(pack=pack, whitelist=whitelist)
        for key, fun in gen.items():
            # if the name (after '.') is "name", then rename to mod_name: fun
            if key[key.index('.') + 1:] == name:
                funcs[key[:key.index('.')]] = fun
        return funcs

    def chop_mods(self):
        '''
        Chop off the module names so that the raw functions are exposed,
        used to generate the grains
        '''
        funcs = {}
        for key, fun in self.gen_functions().items():
            funcs[key[key.rindex('.')] + 1:] = fun
        return funcs

    def gen_grains(self, force_refresh=False):
        '''
        Read the grains directory and execute all of the public callable
        members. Then verify that the returns are python dict's and return
        a dict containing all of the returned values.
        '''
        if self.opts.get('grains_cache', False):
            cfn = os.path.join(
                self.opts['cachedir'],
                '{0}.cache.p'.format('grains')
            )
            if os.path.isfile(cfn):
                grains_cache_age = int(time.time() - os.path.getmtime(cfn))
                if self.opts.get('grains_cache_expiration', 300) >= grains_cache_age and not \
                        self.opts.get('refresh_grains_cache', False) and not force_refresh:
                    log.debug('Retrieving grains from cache')
                    try:
                        with salt.utils.fopen(cfn, 'rb') as fp_:
                            cached_grains = self.serial.load(fp_)
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
                                      self.opts.get('grains_cache_expiration', 300)
                                  ))
            else:
                log.debug('Grains cache file does not exist.')
        grains_data = {}
        funcs = self.gen_functions()
        for key, fun in funcs.items():
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
            # The OrderedDict of funcs has core grains at the end. So earlier
            # grains are the ones which should override
            ret.update(grains_data)
            grains_data = ret
        # Write cache if enabled
        if self.opts.get('grains_cache', False):
            cumask = os.umask(077)
            try:
                if salt.utils.is_windows():
                    # Make sure cache file isn't read-only
                    __salt__['cmd.run']('attrib -R "{0}"'.format(cfn))
                with salt.utils.fopen(cfn, 'w+b') as fp_:
                    try:
                        self.serial.dump(grains_data, fp_)
                    except TypeError:
                        # Can't serialize pydsl
                        pass
            except (IOError, OSError):
                msg = 'Unable to write to grains cache file {0}'
                log.error(msg.format(cfn))
            os.umask(cumask)
        return grains_data


class LazyLoader(MutableMapping):
    '''
    Lazily load things modules. If anyone asks for len or attempts to iterate this
    will load them all.

    TODO: negative caching? If you ask for 'foo.bar' and it doesn't exist it will
    look EVERY time unless someone calls load_all()
    '''
    def __init__(self,
                 loader,
                 functions=None,
                 pack=None,
                 whitelist=None):
        # create a dict to store module functions in
        self._dict = {}

        self.loader = loader
        if not functions:
            self.functions = {}
        else:
            self.functions = functions
        self.pack = pack
        self.whitelist = whitelist

        # have we already loded everything?
        self.loaded = False

    def _load(self, key):
        '''
        Load a single item if you have it
        '''
        # if the key doesn't have a '.' then it isn't valid for this mod dict
        if '.' not in key:
            raise KeyError
        mod_key = key.split('.', 1)[0]
        if self.whitelist:
            # if the modulename isn't in the whitelist, don't bother
            if mod_key not in self.whitelist:
                raise KeyError
        mod_funcs = self.loader.gen_module(mod_key,
                                           self.functions,
                                           pack=self.pack,
                                           )
        # if you loaded nothing, then we don't have it
        if mod_funcs is None:
            # if we couldn't find it, then it could be a virtual or we don't have it
            # until we have a better way, we have to load them all to know
            # TODO: maybe do a load until, with some glob match first?
            self.load_all()
            return self._dict[key]
        self._dict.update(mod_funcs)

    def load_all(self):
        '''
        Load all of them
        '''
        self._dict.update(self.loader.gen_functions(pack=self.pack,
                                                    whitelist=self.whitelist))
        self.loaded = True

    def __setitem__(self, key, val):
        self._dict[key] = val

    def __delitem__(self, key):
        del self._dict[key]

    def __getitem__(self, key):
        '''
        Check if the key is ttld out, then do the get
        '''
        if key not in self._dict and not self.loaded:
            # load the item
            self._load(key)
            log.debug('LazyLoaded {0}'.format(key))
        return self._dict[key]

    def __len__(self):
        # if not loaded,
        if not self.loaded:
            self.load_all()
        return len(self._dict)

    def __iter__(self):
        if not self.loaded:
            self.load_all()
        return iter(self._dict)


class LazyFilterLoader(LazyLoader):
    '''
    Subclass of LazyLoader which filters the module names (for things such as ext_pillar)
    which have all modules with a single function that we care about
    '''
    def __init__(self,
                 loader,
                 name,
                 functions=None,
                 pack=None,
                 whitelist=None):
        self.name = name
        LazyLoader.__init__(self,
                            loader,
                            functions=functions,
                            pack=pack,
                            whitelist=whitelist)

    def _load(self, key):
        if self.whitelist:
            # if the modulename isn't in the whitelist, don't bother
            if key not in self.whitelist:
                raise KeyError
        mod_funcs = self.loader.gen_module(key,
                                           self.functions,
                                           pack=self.pack,
                                           )
        # if you loaded nothing, then we don't have it
        if mod_funcs is None:
            # if we couldn't find it, then it could be a virtual or we don't have it
            # until we have a better way, we have to load them all to know
            # TODO: maybe do a load until, with some glob match first?
            self.load_all()
            return self._dict[key]

        # if we got one, now lets check if we have the function name we want
        for mod_key, mod_fun in mod_funcs.iteritems():
            # if the name (after '.') is "name", then rename to mod_name: fun
            if mod_key[mod_key.index('.') + 1:] == self.name:
                self._dict[mod_key[:mod_key.index('.')]] = mod_fun

    def load_all(self):
        filtered_funcs = self.loader.filter_func(self.name,
                                                 pack=self.pack,
                                                 whitelist=self.whitelist)
        self._dict.update(filtered_funcs)
