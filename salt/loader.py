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

# Import salt libs
from salt.exceptions import LoaderError
from salt.template import check_render_pipe_str
from salt.utils.decorators import Depends

log = logging.getLogger(__name__)

SALT_BASE_PATH = os.path.dirname(salt.__file__)
LOADED_BASE_NAME = 'salt.loaded'


def _create_loader(
        opts,
        ext_type,
        tag,
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
    if base_path:
        sys_types = os.path.join(base_path, ext_type)
    else:
        sys_types = os.path.join(SALT_BASE_PATH, ext_type)
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
        if (os.path.isdir(maybe_dir)):
            cli_module_dirs.insert(0, maybe_dir)
            continue

        maybe_dir = os.path.join(_dir, '_{0}'.format(ext_type))
        if (os.path.isdir(maybe_dir)):
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
    Returns the minion modules
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
        whitelist=whitelist
    )
    # Enforce dependencies of module functions from "functions"
    Depends.enforce_dependencies(functions)

    if opts.get('providers', False):
        if isinstance(opts['providers'], dict):
            for mod, provider in opts['providers'].items():
                funcs = raw_mod(opts, provider, functions)
                if funcs:
                    for func in funcs:
                        f_key = '{0}{1}'.format(mod, func[func.rindex('.'):])
                        functions[f_key] = funcs[func]
    return functions


def raw_mod(opts, name, functions):
    '''
    Returns a single module loaded raw and bypassing the __virtual__ function
    '''
    load = _create_loader(opts, 'modules', 'rawmodule')
    return load.gen_module(name, functions)


def returners(opts, functions, whitelist=None):
    '''
    Returns the returner modules
    '''
    load = _create_loader(opts, 'returners', 'returner')
    pack = {'name': '__salt__',
            'value': functions}
    return load.gen_functions(pack, whitelist=whitelist)


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
    if not 'master_tops' in opts:
        return {}
    whitelist = opts['master_tops'].keys()
    load = _create_loader(opts, 'tops', 'top')
    return load.filter_func('top', whitelist=whitelist)


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
    ret = load.gen_functions(whitelist=backends)
    return ret


def states(opts, functions, whitelist=None):
    '''
    Returns the state modules
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
    return load.gen_functions(pack, whitelist=whitelist)


def render(opts, functions):
    '''
    Returns the render modules
    '''
    load = _create_loader(
        opts, 'renderers', 'render', ext_type_dirs='render_dirs'
    )
    pack = {'name': '__salt__',
            'value': functions}
    rend = load.filter_func('render', pack)
    if not check_render_pipe_str(opts['renderer'], rend):
        err = ('The renderer {0} is unavailable, this error is often because '
               'the needed software is unavailable'.format(opts['renderer']))
        log.critical(err)
        raise LoaderError(err)
    return rend


def grains(opts):
    '''
    Return the functions for the dynamic grains and the values for the static
    grains.
    '''
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

    load = _create_loader(opts, 'grains', 'grain', ext_dirs=False)
    grains_info = load.gen_grains()
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
    def __init__(self, module_dirs, opts=None, tag='module',
                 loaded_base_name=None, mod_type_check=None):
        self.module_dirs = module_dirs
        if opts is None:
            opts = {}
        if '_' in tag:
            raise LoaderError('Cannot tag loader with an "_"')
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
                    import pyximport
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
            else:
                for ext in ('.py', '.pyo', '.pyc', '.so'):
                    full_test = '{0}{1}'.format(fn_, ext)
                    if os.path.isfile(full_test):
                        full = full_test
        if not full:
            return None

        cython_enabled = False
        if self.opts.get('cython_enable', True) is True:
            try:
                import pyximport
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
                functions[functions.keys()[0]].__module__
            ].__context__
        except AttributeError:
            context = {}
        mod.__context__ = context
        return funcs

    def gen_functions(self, pack=None, virtual_enable=True, whitelist=None):
        '''
        Return a dict of functions found in the defined module_dirs
        '''
        log.debug('loading {0} in {1}'.format(self.tag, self.module_dirs))
        names = {}
        modules = []
        funcs = {}
        disable = set(self.opts.get('disable_{0}s'.format(self.tag), []))

        cython_enabled = False
        if self.opts.get('cython_enable', True) is True:
            try:
                import pyximport
                pyximport.install()
                cython_enabled = True
            except ImportError:
                log.info('Cython is enabled in the options but not present '
                         'in the system path. Skipping Cython modules.')
        for mod_dir in self.module_dirs:
            if not os.path.isabs(mod_dir):
                log.debug(
                    'Skipping {0}, it is not an absolute path'.format(
                        mod_dir
                    )
                )
                continue
            if not os.path.isdir(mod_dir):
                log.debug(
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
                    log.debug(
                        'Skipping {0}, it is disabled by configuration'.format(
                            fn_
                        )
                    )
                    continue
                if (fn_.endswith(('.py', '.pyc', '.pyo', '.so'))
                        or (cython_enabled and fn_.endswith('.pyx'))
                        or os.path.isdir(os.path.join(mod_dir, fn_))):

                    extpos = fn_.rfind('.')
                    if extpos > 0:
                        _name = fn_[:extpos]
                    else:
                        _name = fn_
                    names[_name] = os.path.join(mod_dir, fn_)
                else:
                    log.debug(
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
            modules.append(mod)
        for mod in modules:
            virtual = ''
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
                # This function will return either a new name for the module,
                # an empty string(won't be loaded but you just need to check
                # against the same python type, a string) or False.
                # This allows us to have things like the pkg module working on
                # all platforms under the name 'pkg'. It also allows for
                # modules like augeas_cfg to be referred to as 'augeas', which
                # would otherwise have namespace collisions. And finally it
                # allows modules to return False if they are not intended to
                # run on the given platform or are missing dependencies.
                try:
                    if hasattr(mod, '__virtual__'):
                        if callable(mod.__virtual__):
                            virtual = mod.__virtual__()
                            if not virtual:
                                # if __virtual__() evaluates to false then the
                                # module wasn't meant for this platform or it's
                                # not supposed to load for some other reason.
                                # Some modules might accidentally return None
                                # and are improperly loaded
                                if virtual is None:
                                    log.warning(
                                        '{0}.__virtual__() is wrongly '
                                        'returning `None`. It should either '
                                        'return `True`, `False` or a new '
                                        'name. If you\'re the developer '
                                        'of the module {1!r}, please fix '
                                        'this.'.format(
                                            mod.__name__,
                                            module_name
                                        )
                                    )
                                continue

                            if virtual is not True and module_name != virtual:
                                # If __virtual__ returned True the module will
                                # be loaded with the same name, if it returned
                                # other value than `True`, it should be a new
                                # name for the module.
                                # Update the module name with the new name
                                log.debug(
                                    'Loaded {0} as virtual {1}'.format(
                                        module_name, virtual
                                    )
                                )
                                module_name = virtual

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
                    log.exception(
                        'Failed to read the virtual function for '
                        '{0}: {1}'.format(
                            self.tag, module_name
                        )
                    )
                    continue

            if whitelist:
                # If a whitelist is defined then only load the module if it is
                # in the whitelist
                if module_name not in whitelist:
                    continue

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

                    # functions are namespaced with their module name
                    module_func_name = '{0}.{1}'.format(module_name, funcname)
                    funcs[module_func_name] = func
                    log.trace(
                        'Added {0} to {1}'.format(module_func_name, self.tag)
                    )
                    self._apply_outputter(func, mod)

        # now that all the functions have been collected, iterate back over
        # the available modules and inject the special __salt__ namespace that
        # contains these functions.
        for mod in modules:
            if not hasattr(mod, '__salt__'):
                mod.__salt__ = funcs
            elif not in_pack(pack, '__salt__'):
                mod.__salt__.update(funcs)
        return funcs

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
        if pack:
            gen = self.gen_functions(pack, whitelist=whitelist)
        else:
            gen = self.gen_functions(whitelist=whitelist)
        for key, fun in gen.items():
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

    def gen_grains(self):
        '''
        Read the grains directory and execute all of the public callable
        members. Then verify that the returns are python dict's and return
        a dict containing all of the returned values.
        '''
        grains_data = {}
        funcs = self.gen_functions()
        for key, fun in funcs.items():
            if key[key.index('.') + 1:] == 'core':
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
        for key, fun in funcs.items():
            if key[key.index('.') + 1:] != 'core':
                continue
            ret = fun()
            if not isinstance(ret, dict):
                continue
            grains_data.update(ret)
        return grains_data
