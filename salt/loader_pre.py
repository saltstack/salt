# -*- coding: utf-8 -*-
'''
Salt loader pre-loader support which auto-discovers extension sub-systems.

The "pre" loader machinery scans through child directories in the salt
directory looking for `.loader.py` (viz. "pre-loader") files.
Directories that have these pre-loader files are salt extension
directories.  The pre-loader files define functions that instantiate
the `LazyLoader` for loading the actual modules from the the
respective extension directory.  pre-loader files can use the symbol
`__this_dir__` to refer to the specific extension directory where they
reside.
'''


from __future__ import absolute_import

import imp
import inspect
import logging
import os
import re

from salt.exceptions import LoaderError
from salt import loader_core
from salt.utils import context


LOG = logging.getLogger(__name__)

PRE_LOADER_FILE = '.loader.py'
MOD_BASE = '{0}.extensions'.format(__name__)


def _find_preloader_files(path):
    '''Recursively find all of the pre-loader files starting in path'''
    loader_fns = set()

    for root, sub_dirs, files in os.walk(path):
        if '.loader.py' in files:
            loader_path = os.path.join(root, '.loader.py')
            if os.path.isfile(loader_path):
                loader_fns.add(loader_path)
    return loader_fns


def _load_ext_preloader(fpath, modbase, modsub):
    '''Instantiate a pre-loader module from a pre-loader file'''
    this_dir = os.path.dirname(fpath)
    mpath = '{0}.{1}'.format(modbase, modsub)
    LOG.debug('Pre-loader: {0} => {1}'.format(fpath, mpath))
    mod = imp.load_source(mpath, fpath)
    setattr(mod, '__this_dir__', this_dir)
    return mod


def _mod_sub(fname, base_path):
    fname_ = os.path.abspath(fname)
    base_path_ = os.path.abspath(base_path)
    if not fname_.startswith(base_path_):
        raise RuntimeError('Extension "{0}" is not a sub-directory of the base "{1}"'.format(fname, base_path))
    dirs = fname[len(base_path):].split(os.path.sep)[1:-1]
    return '.'.join(dirs)


def load_all_loaders(base_path, sym_dict=None, fpath=None):
    '''
    Recursively search from base_path for extension loader files and
    load them into the symbol dictionary `sym_dict`
    '''
    if sym_dict is None:
        sym_dict = {}

    loaded = {}
    inits = []
    fnames = sorted(_find_preloader_files(base_path))
    loader_core._generate_module(MOD_BASE)
    try:
        mods = [_load_ext_preloader(fn, MOD_BASE, _mod_sub(fn, base_path)) for fn in fnames]
    except ImportError as exc:
        # FIXME: should the below LOG.warn() instead of raise?
        raise LoaderError('Pre-loader: failed to load: {0}'.format(exc))

    for mod in mods:
        if inspect.isfunction(mod.__init__):
            inits.append(mod.__init__)

        for func in LoaderFunc.loader_mods[mod.__name__]:
            name = func.__name__
            if name in sym_dict:
                # FIXME: should the below LOG.warn() instead of raise?
                raise LoaderError('Pre-loader: Import collision of "{0}" from "{1}" with "{2}"'.format(
                    name, mod.__file__, loaded.get(name, sym_dict.get('__file__', fpath))
                ))
            sym_dict[name] = getattr(mod, name)
            loaded[name] = mod.__file__
    for init in inits:
        try:
            init()
        except Exception as exc:
            # FIXME: should the below LOG.warn() instead of raise?
            raise LoaderError('Initialization of __init__() in "{0}" failed: {1}'.format(
                init.func_code.co_filename, exc
            ))

    return sym_dict


class LoaderFunc(object):
    '''
    Decorator for marking loader functions in `.loader.py` files and
    providing the functions in the `salt.loader` namespace.
    '''
    loaders = {}
    loader_mods = {}

    def __init__(self, func):
        if not inspect.isfunction(func):
            raise TypeError('{0} must be used as a function decorator'.format(self.__class__.__name__))
        self.func = func
        self.loaders[func.__name__] = func
        self.loader_mods.setdefault(func.__module__, set()).add(func)

    def __call__(self, *args, **kwargs):
        with context.func_globals_inject(self.func, **self.loaders):
            return self.func(*args, **kwargs)
