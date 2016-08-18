# -*- coding: utf-8 -*-
'''The Salt loader is the core to Salt's plugin system, the loader scans
directories for python loadable code and organizes the code into the
plugin interfaces used by Salt.

Core functions are contained here and should only be used through
salt.loader.
'''

# Import python libs
from __future__ import absolute_import
import os
import imp
import sys
import time
import logging
import inspect
import tempfile
import functools
from collections import MutableMapping
from zipimport import zipimporter

# Import 3rd-party libs
try:
    import pkg_resources
    HAS_PKG_RESOURCES = True
except ImportError:
    HAS_PKG_RESOURCES = False
import salt.ext.six as six

# Import salt libs
from salt.utils.decorators import Depends
import salt.utils.context
import salt.utils.lazy
import salt.utils.event
import salt.utils.odict

# Solve the Chicken and egg problem where grains need to run before any
# of the modules are loaded and are generally available for any usage.
import salt.modules.cmdmod

__salt__ = {
    'cmd.run': salt.modules.cmdmod._run_quiet
}
log = logging.getLogger(__name__)

SALT_BASE_PATH = os.path.abspath(os.path.dirname(salt.__file__))
LOADED_BASE_NAME = 'salt.loaded'

if six.PY3:
    # pylint: disable=no-member,no-name-in-module,import-error
    import importlib.machinery
    SUFFIXES = []
    for suffix in importlib.machinery.EXTENSION_SUFFIXES:
        SUFFIXES.append((suffix, 'rb', 3))
    for suffix in importlib.machinery.BYTECODE_SUFFIXES:
        SUFFIXES.append((suffix, 'rb', 2))
    for suffix in importlib.machinery.SOURCE_SUFFIXES:
        SUFFIXES.append((suffix, 'r', 1))
    # pylint: enable=no-member,no-name-in-module,import-error
else:
    SUFFIXES = imp.get_suffixes()

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
        module_dirs(
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


def module_dirs(
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
    ext_types = os.path.join(opts['extension_modules'], ext_type)

    ext_type_types = []
    if ext_dirs:
        if ext_type_dirs is None:
            ext_type_dirs = '{0}_dirs'.format(tag)
        if ext_type_dirs in opts:
            ext_type_types.extend(opts[ext_type_dirs])
        if HAS_PKG_RESOURCES and ext_type_dirs:
            for entry_point in pkg_resources.iter_entry_points('salt.loader', ext_type_dirs):
                loaded_entry_point = entry_point.load()
                for path in loaded_entry_point():
                    ext_type_types.append(path)

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
    loader = LazyLoader(
        module_dirs(opts, mod, 'rawmodule'),
        opts,
        tag='rawmodule',
        virtual_enable=False,
        pack={'__salt__': functions},
    )
    # if we don't have the module, return an empty dict
    if name not in loader.file_mapping:
        return {}

    loader._load_module(name)  # load a single module (the one passed in)
    return dict(loader._dict)  # return a copy of *just* the funcs for `name`


# TODO: get rid of? Does anyone use this? You should use raw() instead
def call(fun, **kwargs):
    '''
    Directly call a function inside a loader directory
    '''
    args = kwargs.get('args', [])
    dirs = kwargs.get('dirs', [])

    funcs = LazyLoader(
        [os.path.join(SALT_BASE_PATH, 'modules')] + dirs,
        None,
        tag='modules',
        virtual_enable=False,
    )
    return funcs[fun](*args)


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

    :returns: A LazyLoader object which functions as a dictionary. Keys are 'module.function' and values
    are function references themselves which are loaded on-demand.
    # TODO:
        - move modules_max_memory into here
        - singletons (per tag)
    '''

    mod_dict_class = salt.utils.odict.OrderedDict

    def __init__(self,
                 module_dirs_,
                 opts=None,
                 tag='module',
                 loaded_base_name=None,
                 mod_type_check=None,
                 pack=None,
                 whitelist=None,
                 virtual_enable=True,
                 static_modules=None,
                 proxy=None
                 ):  # pylint: disable=W0231
        '''
        In pack, if any of the values are None they will be replaced with an
        empty context-specific dict
        '''

        self.inject_globals = {}
        self.pack = {} if pack is None else pack
        if opts is None:
            opts = {}
        self.context_dict = salt.utils.context.ContextDict()
        self.opts = self.__prep_mod_opts(opts)

        self.module_dirs = module_dirs_
        self.tag = tag
        self.loaded_base_name = loaded_base_name or LOADED_BASE_NAME
        self.mod_type_check = mod_type_check or _mod_type

        if '__context__' not in self.pack:
            self.pack['__context__'] = None

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

        self.disabled = set(self.opts.get('disable_{0}s'.format(self.tag), []))

        self.refresh_file_mapping()

        super(LazyLoader, self).__init__()  # late init the lazy loader
        # create all of the import namespaces
        _generate_module('{0}.int'.format(self.loaded_base_name))
        _generate_module('{0}.int.{1}'.format(self.loaded_base_name, tag))
        _generate_module('{0}.ext'.format(self.loaded_base_name))
        _generate_module('{0}.ext.{1}'.format(self.loaded_base_name, tag))

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
        mod_name = function_name.split('.')[0]
        if mod_name in self.loaded_modules:
            return '\'{0}\' is not available.'.format(function_name)
        else:
            try:
                reason = self.missing_modules[mod_name]
            except KeyError:
                return '\'{0}\' is not available.'.format(function_name)
            else:
                if reason is not None:
                    return '\'{0}\' __virtual__ returned False: {1}'.format(mod_name, reason)
                else:
                    return '\'{0}\' __virtual__ returned False'.format(mod_name)

    def refresh_file_mapping(self):
        '''
        refresh the mapping of the FS on disk
        '''
        # map of suffix to description for imp
        self.suffix_map = {}
        suffix_order = ['']  # local list to determine precedence of extensions
                             # Prefer packages (directories) over modules (single files)!
        for (suffix, mode, kind) in SUFFIXES:
            self.suffix_map[suffix] = (suffix, mode, kind)
            suffix_order.append(suffix)

        if self.opts.get('cython_enable', True) is True:
            try:
                global pyximport
                pyximport = __import__('pyximport')  # pylint: disable=import-error
                pyximport.install()
                # add to suffix_map so file_mapping will pick it up
                self.suffix_map['.pyx'] = tuple()
            except ImportError:
                log.info('Cython is enabled in the options but not present '
                    'in the system path. Skipping Cython modules.')
        # Allow for zipimport of modules
        if self.opts.get('enable_zip_modules', True) is True:
            self.suffix_map['.zip'] = tuple()
        # allow for module dirs
        self.suffix_map[''] = ('', '', imp.PKG_DIRECTORY)

        # create mapping of filename (without suffix) to (path, suffix)
        # The files are added in order of priority, so order *must* be retained.
        self.file_mapping = salt.utils.odict.OrderedDict()

        for mod_dir in self.module_dirs:
            files = []
            try:
                files = os.listdir(mod_dir)
            except OSError:
                continue  # Next mod_dir
            for filename in files:
                try:
                    if filename.startswith('_'):
                        # skip private modules
                        # log messages omitted for obviousness
                        continue  # Next filename
                    f_noext, ext = os.path.splitext(filename)
                    # make sure it is a suffix we support
                    if ext not in self.suffix_map:
                        continue  # Next filename
                    if f_noext in self.disabled:
                        log.trace(
                            'Skipping {0}, it is disabled by configuration'.format(
                            filename
                            )
                        )
                        continue  # Next filename
                    fpath = os.path.join(mod_dir, filename)
                    # if its a directory, lets allow us to load that
                    if ext == '':
                        # is there something __init__?
                        subfiles = os.listdir(fpath)
                        for suffix in suffix_order:
                            if '' == suffix:
                                continue  # Next suffix (__init__ must have a suffix)
                            init_file = '__init__{0}'.format(suffix)
                            if init_file in subfiles:
                                break
                        else:
                            continue  # Next filename

                    if f_noext in self.file_mapping:
                        curr_ext = self.file_mapping[f_noext][1]
                        #log.debug("****** curr_ext={0} ext={1} suffix_order={2}".format(curr_ext, ext, suffix_order))
                        if '' in (curr_ext, ext) and curr_ext != ext:
                            log.error(
                                'Module/package collision: \'%s\' and \'%s\'',
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
            f_noext = smod.split('.')[-1]
            self.file_mapping[f_noext] = (smod, '.o')

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
        if '__grains__' not in self.pack:
            self.context_dict['grains'] = opts.get('grains', {})
            self.pack['__grains__'] = salt.utils.context.NamespacedDictWrapper(self.context_dict, 'grains', override_name='grains')

        if '__pillar__' not in self.pack:
            self.context_dict['pillar'] = opts.get('pillar', {})
            self.pack['__pillar__'] = salt.utils.context.NamespacedDictWrapper(self.context_dict, 'pillar', override_name='pillar')

        mod_opts = {}
        for key, val in list(opts.items()):
            if key == 'logger':
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
        fpath_dirname = os.path.dirname(fpath)
        try:
            sys.path.append(fpath_dirname)
            if suffix == '.pyx':
                mod = pyximport.load_module(name, fpath, tempfile.gettempdir())
            elif suffix == '.o':
                top_mod = __import__(fpath, globals(), locals(), [])
                comps = fpath.split('.')
                if len(comps) < 2:
                    mod = top_mod
                else:
                    mod = top_mod
                    for subname in comps[1:]:
                        mod = getattr(mod, subname)
            elif suffix == '.zip':
                mod = zipimporter(fpath).load_module(name)
            else:
                desc = self.suffix_map[suffix]
                # if it is a directory, we don't open a file
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
                    with salt.utils.fopen(fpath, desc[1]) as fn_:
                        mod = imp.load_module(
                            '{0}.{1}.{2}.{3}'.format(
                                self.loaded_base_name,
                                self.mod_type_check(fpath),
                                self.tag,
                                name
                            ), fn_, fpath, desc)

        except IOError:
            raise
        except ImportError as exc:
            if 'magic number' in str(exc):
                log.warning('Failed to import {0} {1}. Bad magic number. If migrating '
                        'from Python2 to Python3, remove all .pyc files and try again.'.format(self.tag, name))
            log.debug(
                'Failed to import {0} {1}:\n'.format(
                    self.tag, name
                ),
                exc_info=True
            )
            return False
        except Exception as error:
            log.error(
                'Failed to import {0} {1}, this is due most likely to a '
                'syntax error:\n'.format(
                    self.tag, name
                ),
                exc_info=True
            )
            return False
        except SystemExit:
            log.error(
                'Failed to import {0} {1} as the module called exit()\n'.format(
                    self.tag, name
                ),
                exc_info=True
            )
            return False
        finally:
            sys.path.remove(fpath_dirname)

        if hasattr(mod, '__opts__'):
            mod.__opts__.update(self.opts)
        else:
            mod.__opts__ = self.opts

        # pack whatever other globals we were asked to
        for p_name, p_value in six.iteritems(self.pack):
            setattr(mod, p_name, p_value)

        module_name = mod.__name__.rsplit('.', 1)[-1]

        # Call a module's initialization method if it exists
        module_init = getattr(mod, '__init__', None)
        if inspect.isfunction(module_init):
            try:
                module_init(self.opts)
            except TypeError as e:
                log.error(e)
            except Exception:
                err_string = '__init__ failed'
                log.debug(
                    'Error loading {0}.{1}: {2}'.format(
                        self.tag,
                        module_name,
                        err_string),
                    exc_info=True)
                self.missing_modules[module_name] = err_string
                self.missing_modules[name] = err_string
                return False

        # if virtual modules are enabled, we need to look for the
        # __virtual__() function inside that module and run it.
        if self.virtual_enable:
            (virtual_ret, module_name, virtual_err) = self.process_virtual(
                mod,
                module_name,
            )
            if virtual_err is not None:
                log.trace('Error loading {0}.{1}: {2}'.format(self.tag,
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
        #
        # Render modules and state modules are OK though
        if 'proxy' in self.opts:
            if self.tag in ['grains', 'proxy']:
                if not hasattr(mod, '__proxyenabled__') or \
                        (self.opts['proxy']['proxytype'] not in mod.__proxyenabled__ and
                            '*' not in mod.__proxyenabled__):
                    err_string = 'not a proxy_minion enabled module'
                    self.missing_modules[module_name] = err_string
                    self.missing_modules[name] = err_string
                    return False

        if getattr(mod, '__load__', False) is not False:
            log.info(
                'The functions from module \'{0}\' are being loaded from the '
                'provided __load__ attribute'.format(
                    module_name
                )
            )

        # If we had another module by the same virtual name, we should put any
        # new functions under the existing dictionary.
        if module_name in self.loaded_modules:
            mod_dict = self.loaded_modules[module_name]
        else:
            mod_dict = self.mod_dict_class()

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
            full_funcname = '{0}.{1}'.format(module_name, funcname)
            # Save many references for lookups
            # Careful not to overwrite existing (higher priority) functions
            if full_funcname not in self._dict:
                self._dict[full_funcname] = func
            if funcname not in mod_dict:
                setattr(mod_dict, funcname, func)
                mod_dict[funcname] = func
                self._apply_outputter(func, mod)

        # enforce depends
        try:
            Depends.enforce_dependencies(self._dict, self.tag)
        except RuntimeError as exc:
            log.info('Depends.enforce_dependencies() failed '
                     'for reasons: {0}'.format(exc))

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
                try:
                    start = time.time()
                    virtual = mod.__virtual__()
                    if isinstance(virtual, tuple):
                        error_reason = virtual[1]
                        virtual = virtual[0]
                    if self.opts.get('virtual_timer', False):
                        end = time.time() - start
                        msg = 'Virtual function took {0} seconds for {1}'.format(
                                end, module_name)
                        log.warning(msg)
                except Exception as exc:
                    error_reason = ('Exception raised when processing __virtual__ function'
                              ' for {0}. Module will not be loaded {1}'.format(
                                  module_name, exc))
                    log.error(error_reason, exc_info_on_loglevel=logging.DEBUG)
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
                            '\'{1}\', please fix this.'.format(
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
                            'The \'{0}\' module is renaming itself in its '
                            '__virtual__() function ({1} => {2}). Please '
                            'set it\'s virtual name as the '
                            '\'__virtualname__\' module attribute. '
                            'Example: "__virtualname__ = \'{2}\'"'.format(
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
                            'The module \'{0}\' is showing some bad usage. Its '
                            '__virtualname__ attribute is set to \'{1}\' yet the '
                            '__virtual__() function is returning \'{2}\'. These '
                            'values should match!'.format(
                                mod.__name__,
                                virtualname,
                                virtual
                            )
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


def global_injector_decorator(inject_globals):
    '''
    Decorator used by the LazyLoader to inject globals into a function at
    execute time.

    globals
        Dictionary with global variables to inject
    '''
    def inner_decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with salt.utils.context.func_globals_inject(func, **inject_globals):
                return func(*args, **kwargs)
        return wrapper
    return inner_decorator
