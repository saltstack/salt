'''
Routines to set up a minion
'''
# Import python libs
import os
import sys
import imp
import distutils.sysconfig

# Import cython
import pyximport; pyximport.install()

def minion_mods(opts):
    '''
    Returns the minion modules
    '''
    module_dirs = [
        os.path.join(distutils.sysconfig.get_python_lib(), 'salt/modules'),
        ] + opts['module_dirs']
    load = Loader(module_dirs, opts)
    return load.gen_functions()

def returners(opts):
    '''
    Returns the returner modules
    '''
    module_dirs = [
        os.path.join(distutils.sysconfig.get_python_lib(), 'salt/returners'),
        ] + opts['returner_dirs']
    load = Loader(module_dirs, opts)
    return load.filter_func('returner')


class Loader(object):
    '''
    Used to load in arbitrairy modules from a directory, the Loader can also be
    used to only load specific functions from a directory, or to call modules
    in an arbitrairy directory directly.
    '''
    def __init__(self, module_dirs, opts={}):
        self.module_dirs = module_dirs
        self.opts = self.__prep_mod_opts(opts)

    def __prep_mod_opts(self, opts):
        '''
        Strip out of the opts any logger instance
        '''
        mod_opts = {}
        for key, val in opts.items():
            if key == 'logger':
                continue
            mod_opts[key] = val
        return mod_opts

    def call(self, fun, arg=[]):
        '''
        Call a function in the load path.
        '''
        name = fun[:fun.rindex('.')]
        fn_, path, desc = imp.find_module(name, self.module_dirs)
        mod = imp.load_module(name, fn_, path, desc)
        return getattr(mod, fun[fun.rindex('.'):])(*arg)

    def gen_functions(self):
        '''
        Return a dict of functions found in the defined module_dirs
        '''
        mods = set()
        funcs = {}
        for mod_dir in self.module_dirs:
            for fn_ in os.listdir(mod_dir):
                if fn_.startswith('_'):
                    continue
                if fn_.endswith('.py')\
                    or fn_.endswith('.pyc')\
                    or fn_.endswith('.pyo')\
                    or fn_.endswith('.so')\
                    or fn_.endswith('.pyx'):
                    mods.add(fn_[:fn_.rindex('.')])
        for name in mods:
            fn_, path, desc = imp.find_module(name, self.module_dirs)
            mod = imp.load_module(name, fn_, path, desc)
            if hasattr(mod, '__opts__'):
                mod.__opts__.update(self.opts)
            else:
                mod.__opts__ = self.opts

            for attr in dir(mod):
                if attr.startswith('_'):
                    continue
                if callable(getattr(mod, attr)):
                    funcs[mod + '.' + attr] = getattr(mod, attr)
        return funcs

    def filter_func(self, name):
        '''
        Filter a specific function out of the functions, this is used to load
        the returners for the salt minion
        '''
        funcs = {}
        for key, fun in self.gen_functions():
            if key[key.rindex('.'):] == name:
                funcs[key[:key.rindex('.')]] = fun
        return funcs
