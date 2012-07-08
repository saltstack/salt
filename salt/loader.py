'''
Routines to set up a minion
'''

# This module still needs package support, so that the functions dict
# returned can send back functions like: foo.bar.baz


# Import python libs
import os
import imp
import salt
import logging
import tempfile

# Import Salt libs
from salt.exceptions import LoaderError

log = logging.getLogger(__name__)
salt_base_path = os.path.dirname(salt.__file__)


def _create_loader(opts, ext_type, tag, ext_dirs=True, ext_type_dirs=None):
    '''
    Creates Loader instance

    Order of module_dirs:
        opts[ext_type_dirs],
        extension types,
        base types.
    '''
    ext_types = os.path.join(opts['extension_modules'], ext_type)
    sys_types = os.path.join(salt_base_path, ext_type)

    ext_type_types = []
    if ext_dirs:
        if ext_type_dirs is None:
            ext_type_dirs = '{0}_dirs'.format(tag)
        if ext_type_dirs in opts:
            ext_type_types.extend(opts[ext_type_dirs])

    module_dirs = ext_type_types + [ext_types, sys_types]
    return Loader(module_dirs, opts, tag)


def minion_mods(opts):
    '''
    Returns the minion modules
    '''
    load = _create_loader(opts, 'modules', 'module')
    functions = load.apply_introspection(load.gen_functions())
    if opts.get('providers', False):
        if isinstance(opts['providers'], dict):
            for mod, provider in opts['providers'].items():
                funcs = raw_mod(opts,
                        provider,
                        functions)
                if funcs:
                    for func in funcs:
                        f_key = '{0}{1}'.format(
                                mod,
                                func[func.rindex('.'):]
                                )
                        functions[f_key] = funcs[func]
    return functions


def raw_mod(opts, name, functions):
    '''
    Returns a single module loaded raw and bypassing the __virtual__ function
    '''
    load = _create_loader(opts, 'modules', 'rawmodule')
    return load.gen_module(name, functions)


def returners(opts):
    '''
    Returns the returner modules
    '''
    load = _create_loader(opts, 'returners', 'returner')
    return load.filter_func('returner')


def pillars(opts, functions):
    '''
    Returns the returner modules
    '''
    load = _create_loader(opts, 'pillar', 'pillar')
    pack = {'name': '__salt__',
            'value': functions}
    return load.filter_func('ext_pillar', pack)


def states(opts, functions):
    '''
    Returns the state modules
    '''
    load = _create_loader(opts, 'states', 'states')
    pack = {'name': '__salt__',
            'value': functions}
    return load.gen_functions(pack)


def render(opts, functions):
    '''
    Returns the render modules
    '''
    load = _create_loader(opts, 'renderers', 'render', ext_type_dirs='render_dirs')
    pack = {'name': '__salt__',
            'value': functions}
    rend = load.filter_func('render', pack)
    if opts['renderer'] not in rend:
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
    if not 'grains' in opts:
        pre_opts = {}
        salt.config.load_config(
                pre_opts,
                opts['conf_file'],
                'SALT_MINION_CONFIG'
                )
        if 'include' in pre_opts:
            pre_opts = salt.config.include_config(
                    pre_opts,
                    opts['conf_file']
                    )
        if 'grains' in pre_opts:
            opts['grains'] = pre_opts['grains']
        else:
            opts['grains'] = {}
    load = _create_loader(opts, 'grains', 'grain', ext_dirs=False)
    grains = load.gen_grains()
    grains.update(opts['grains'])
    return grains


def call(fun, **kwargs):
    '''
    Directly call a function inside a loader directory
    '''
    args = kwargs.get('args', [])
    dirs = kwargs.get('dirs', [])
    module_dirs = [
        os.path.join(salt_base_path, 'modules'),
        ] + dirs
    load = Loader(module_dirs)
    return load.call(fun, args)


def runner(opts):
    '''
    Directly call a function inside a loader directory
    '''
    load = _create_loader(
            opts,
            'runners',
            'runner',
            ext_type_dirs='runner_dirs'
            )
    return load.gen_functions()


class Loader(object):
    '''
    Used to load in arbitrary modules from a directory, the Loader can
    also be used to only load specific functions from a directory, or to
    call modules in an arbitrary directory directly.
    '''
    def __init__(self, module_dirs, opts=dict(), tag='module'):
        self.module_dirs = module_dirs
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

    def get_docs(self, funcs, module=''):
        '''
        Return a dict containing all of the doc strings in the functions dict
        '''
        docs = {}
        for fun in funcs:
            if fun.startswith(module):
                docs[fun] = funcs[fun].__doc__
        return docs

    def call(self, fun, arg=list()):
        '''
        Call a function in the load path.
        '''
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
                    log.info("Cython is enabled in options though it's not "
                             "present in the system path. Skipping Cython "
                             "modules.")
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
            if full.endswith('.pyx'):
                # If there's a name which ends in .pyx it means the above
                # cython_enabled is True. Continue...
                mod = pyximport.load_module(name, full, tempfile.gettempdir())
            else:
                fn_, path, desc = imp.find_module(name, self.module_dirs)
                mod = imp.load_module(
                        '{0}_{1}'.format(name, self.tag),
                        fn_,
                        path,
                        desc
                        )
        except ImportError as exc:
            log.debug(('Failed to import module {0}: {1}').format(name, exc))
            return mod
        except Exception as exc:
            log.warning(('Failed to import module {0}, this is due most'
                ' likely to a syntax error: {1}').format(name, exc))
            return mod
        if hasattr(mod, '__opts__'):
            mod.__opts__.update(self.opts)
        else:
            mod.__opts__ = self.opts

        mod.__grains__ = self.grains

        if pack:
            if isinstance(pack, list):
                for chunk in pack:
                    setattr(mod, chunk['name'], chunk['value'])
            else:
                setattr(mod, pack['name'], pack['value'])

        # Call a module's initialization method if it exists
        if hasattr(mod, '__init__'):
            if callable(mod.__init__):
                try:
                    mod.__init__()
                except TypeError:
                    pass
        funcs = {}
        for attr in dir(mod):
            if attr.startswith('_'):
                continue
            if callable(getattr(mod, attr)):
                func = getattr(mod, attr)
                if hasattr(func, '__bases__'):
                    if 'BaseException' in func.__bases__:
                        # the callable object is an exception, don't load it
                        continue
                funcs[
                        '{0}.{1}'.format(
                            mod.__name__[:mod.__name__.rindex('_')],
                            attr)
                        ] = func
                self._apply_outputter(func, mod)
        if not hasattr(mod, '__salt__'):
            mod.__salt__ = functions
        return funcs

    def gen_functions(self, pack=None, virtual_enable=True):
        '''
        Return a dict of functions found in the defined module_dirs
        '''
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
                continue
            if not os.path.isdir(mod_dir):
                continue
            for fn_ in os.listdir(mod_dir):
                if fn_.startswith('_'):
                    continue
                if fn_.split('.')[0] in disable:
                    continue
                if (fn_.endswith(('.py', '.pyc', '.pyo', '.so'))
                    or (cython_enabled and fn_.endswith('.pyx'))):
                    names[fn_[:fn_.rindex('.')]] = os.path.join(mod_dir, fn_)
        for name in names:
            try:
                if names[name].endswith('.pyx'):
                    # If there's a name which ends in .pyx it means the above
                    # cython_enabled is True. Continue...
                    mod = pyximport.load_module(
                            '{0}_{1}'.format(name, self.tag),
                            names[name],
                            tempfile.gettempdir())
                else:
                    fn_, path, desc = imp.find_module(name, self.module_dirs)
                    mod = imp.load_module(
                            '{0}_{1}'.format(name, self.tag),
                            fn_,
                            path,
                            desc
                            )
            except ImportError as exc:
                log.debug(('Failed to import module {0}, this is most likely'
                           ' NOT a problem: {1}').format(name, exc))
                continue
            except Exception as exc:
                log.warning(('Failed to import module {0}, this is due most'
                    ' likely to a syntax error: {1}').format(name, exc))
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
                        setattr(mod, chunk['name'], chunk['value'])
                else:
                    setattr(mod, pack['name'], pack['value'])

            # Call a module's initialization method if it exists
            if hasattr(mod, '__init__'):
                if callable(mod.__init__):
                    try:
                        mod.__init__()
                    except TypeError:
                        pass

            if virtual_enable:
                if hasattr(mod, '__virtual__'):
                    if callable(mod.__virtual__):
                        virtual = mod.__virtual__()

            for attr in dir(mod):
                if attr.startswith('_'):
                    continue
                if callable(getattr(mod, attr)):
                    func = getattr(mod, attr)
                    if isinstance(func, type):
                        if any([
                            'Error' in func.__name__,
                            'Exception' in func.__name__]):
                            continue
                    if virtual:
                        funcs['{0}.{1}'.format(virtual, attr)] = func
                        self._apply_outputter(func, mod)
                    elif virtual is False:
                        pass
                    else:
                        funcs[
                                '{0}.{1}'.format(
                                    mod.__name__[:mod.__name__.rindex('_')],
                                    attr)
                                ] = func
                        self._apply_outputter(func, mod)
        for mod in modules:
            if not hasattr(mod, '__salt__'):
                mod.__salt__ = funcs
        return funcs

    def _apply_outputter(self, func, mod):
        '''
        Apply the __outputter__ variable to the functions
        '''
        if hasattr(mod, '__outputter__'):
            outp = mod.__outputter__
            if func.__name__ in outp:
                func.__outputter__ = outp[func.__name__]

    def apply_introspection(self, funcs):
        '''
        Pass in a function object returned from get_functions to load in
        introspection functions.
        '''
        funcs['sys.list_functions'] = lambda: self.list_funcs(funcs)
        funcs['sys.list_modules'] = lambda: self.list_modules(funcs)
        funcs['sys.doc'] = lambda module = '': self.get_docs(funcs, module)
        funcs['sys.reload_modules'] = lambda: True
        return funcs

    def list_funcs(self, funcs):
        '''
        List the functions
        '''
        return sorted(funcs)

    def list_modules(self, funcs):
        '''
        List the modules
        '''
        modules = set()
        for key in funcs:
            comps = key.split('.')
            if len(comps) < 2:
                continue
            modules.add(comps[0])
        return sorted(list(modules))

    def filter_func(self, name, pack=None):
        '''
        Filter a specific function out of the functions, this is used to load
        the returners for the salt minion
        '''
        funcs = {}
        gen = self.gen_functions(pack) if pack else self.gen_functions()
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
        grains = {}
        funcs = self.gen_functions()
        for key, fun in funcs.items():
            if not key[key.index('.') + 1:] == 'core':
                continue
            ret = fun()
            if not isinstance(ret, dict):
                continue
            grains.update(ret)
        for key, fun in funcs.items():
            if key[key.index('.') + 1:] == 'core':
                continue
            try:
                ret = fun()
            except Exception as exc:
                log.critical(('Failed to load grains defined in grain file '
                              '{0} in function {1}, error: {2}').format(
                                  key, fun, exc))
                continue
            if not isinstance(ret, dict):
                continue
            grains.update(ret)
        return grains
