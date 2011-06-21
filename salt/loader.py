'''
Routines to set up a minion
'''
# This module still needs package support, so that the functions dict returned
# can send back functions like: foo.bar.baz

# Import python libs
import os
import sys
import imp
import logging
import salt

log = logging.getLogger(__name__)

salt_base_path = os.path.dirname(salt.__file__)

def minion_mods(opts):
    '''
    Returns the minion modules
    '''
    module_dirs = [
        os.path.join(salt_base_path, 'modules'),
        ] + opts['module_dirs']
    load = Loader(module_dirs, opts)
    return load.apply_introspection(load.gen_functions())

def returners(opts):
    '''
    Returns the returner modules
    '''
    module_dirs = [
        os.path.join(salt_base_path, 'returners'),
        ] + opts['returner_dirs']
    load = Loader(module_dirs, opts)
    return load.filter_func('returner')

def states(opts, functions):
    '''
    Returns the returner modules
    '''
    module_dirs = [
        os.path.join(salt_base_path, 'states'),
        ] + opts['states_dirs']
    load = Loader(module_dirs, opts)
    pack = {'name': '__salt__',
            'value': functions}
    return load.gen_functions(pack)

def render(opts, functions):
    '''
    Returns the render modules
    '''
    module_dirs = [
        os.path.join(salt_base_path, 'renderers'),
        ] + opts['render_dirs']
    load = Loader(module_dirs, opts)
    pack = {'name': '__salt__',
            'value': functions}
    return load.filter_func('render', pack)

def grains(opts):
    '''
    Return the functions for the dynamic grains and the values for the static
    grains.
    '''
    module_dirs = [
        os.path.join(salt_base_path, 'grains'),
        ]
    load = Loader(module_dirs, opts)
    return load.gen_grains()

def call(fun, args=[], dirs=[]):
    '''
    Directly call a function inside a loader directory
    '''
    module_dirs = [
        os.path.join(salt_base_path, 'modules'),
        ] + dirs
    load = Loader(module_dirs)
    return load.call(fun, args)

def runner(opts):
    '''
    Directly call a function inside a loader directory
    '''
    module_dirs = [
        os.path.join(salt_base_path, 'runners'),
        ]
    load = Loader(module_dirs, opts)
    return load.gen_functions()


class Loader(object):
    '''
    Used to load in arbitrary modules from a directory, the Loader can also be
    used to only load specific functions from a directory, or to call modules
    in an arbitrary directory directly.
    '''
    def __init__(self, module_dirs, opts={}):
        self.module_dirs = module_dirs
        if opts.has_key('grains'):
            self.grains = opts['grains']
        else:
            self.grains = {}
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

    def call(self, fun, arg=[]):
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

    def gen_functions(self, pack=None):
        '''
        Return a dict of functions found in the defined module_dirs
        '''
        names = {}
        modules = []
        funcs = {}

        cython_enabled = False
        if self.opts.get('cython_enable', True) is True:
            try:
                import pyximport
                pyximport.install()
                cython_enabled = True
            except ImportError:
                log.info("Cython is enabled in options though it's not present "
                         "in the system path. Skipping Cython modules.")
        for mod_dir in self.module_dirs:
            if not mod_dir.startswith('/'):
                continue
            if not os.path.isdir(mod_dir):
                continue
            for fn_ in os.listdir(mod_dir):
                if fn_.startswith('_'):
                    continue
                if fn_.endswith('.py')\
                    or fn_.endswith('.pyc')\
                    or fn_.endswith('.pyo')\
                    or fn_.endswith('.so')\
                    or (cython_enabled and fn_.endswith('.pyx')):
                    names[fn_[:fn_.rindex('.')]] = os.path.join(mod_dir, fn_)
        for name in names:
            try:
                if names[name].endswith('.pyx'):
                    # If there's a name which ends in .pyx it means the above
                    # cython_enabled is True. Continue...
                    mod = pyximport.load_module(name, names[name], '/tmp')
                else:
                    fn_, path, desc = imp.find_module(name, self.module_dirs)
                    mod = imp.load_module(name, fn_, path, desc)
            except ImportError:
                continue
            modules.append(mod)
        for mod in modules:
            virtual = ''
            if hasattr(mod, '__opts__'):
                mod.__opts__.update(self.opts)
            else:
                mod.__opts__ = self.opts

            mod.__grains__ = self.grains

            if pack:
                if type(pack) == type(list()):
                    for chunk in pack:
                        setattr(mod, chunk['name'], chunk['value'])
                else:
                    setattr(mod, pack['name'], pack['value'])

            if hasattr(mod, '__virtual__'):
                if callable(mod.__virtual__):
                    virtual = mod.__virtual__()

            for attr in dir(mod):
                if attr.startswith('_'):
                    continue
                if callable(getattr(mod, attr)):
                    if virtual:
                        funcs[virtual + '.' + attr] = getattr(mod, attr)
                    elif virtual == False:
                        pass
                    else:
                        funcs[mod.__name__ + '.' + attr] = getattr(mod, attr)
        for mod in modules:
            if not hasattr(mod, '__salt__'):
                mod.__salt__ = funcs
        return funcs

    def apply_introspection(self, funcs):
        '''
        Pass in a function object returned from get_functions to load in
        introspection functions.
        '''
        funcs['sys.list_functions'] = lambda: self.list_funcs(funcs)
        funcs['sys.list_modules'] = lambda: funcs.keys
        funcs['sys.doc'] = lambda module = '': self.get_docs(funcs, module)
        return funcs

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
        Chop off the module names so that the raw functions are exposed, used
        to generate the grains
        '''
        funcs = {}
        for key, fun in self.gen_functions().items():
            funcs[key[key.rindex('.')] + 1:] = fun
        return funcs

    def gen_grains(self):
        '''
        Read the grains directory and execute all of the public callable
        members. then verify that the returns are python dict's and return a
        dict containing all of the returned values.
        '''
        grains = {}
        funcs = self.gen_functions()
        for key, fun in funcs.items():
            if not key[key.index('.') + 1:] == 'core':
                continue
            ret = fun()
            if not type(ret) == type(dict()):
                continue
            grains.update(ret)
        for key, fun in funcs.items():
            if key[key.index('.') + 1:] == 'core':
                continue
            ret = fun()
            if not type(ret) == type(dict()):
                continue
            grains.update(ret)
        return grains

