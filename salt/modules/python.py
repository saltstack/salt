# -*- coding: utf-8 -*-
'''
Run python scripts inside salt.

.. versionadded:: Oxygen
'''
import os
import sys
import traceback

if sys.version_info[:2] >= (3, 5):
    import importlib.machinery  # pylint: disable=no-name-in-module,import-error
    import importlib.util  # pylint: disable=no-name-in-module,import-error
    USE_IMPORTLIB = True
else:
    import imp
    USE_IMPORTLIB = False

if USE_IMPORTLIB:
    # pylint: disable=no-member
    MODULE_KIND_SOURCE = 1
    MODULE_KIND_COMPILED = 2
    MODULE_KIND_EXTENSION = 3
    MODULE_KIND_PKG_DIRECTORY = 5
    SUFFIXES = []
    for suffix in importlib.machinery.EXTENSION_SUFFIXES:
        SUFFIXES.append((suffix, u'rb', MODULE_KIND_EXTENSION))
    for suffix in importlib.machinery.BYTECODE_SUFFIXES:
        SUFFIXES.append((suffix, u'rb', MODULE_KIND_COMPILED))
    for suffix in importlib.machinery.SOURCE_SUFFIXES:
        SUFFIXES.append((suffix, u'rb', MODULE_KIND_SOURCE))
    MODULE_KIND_MAP = {
        MODULE_KIND_SOURCE: importlib.machinery.SourceFileLoader,
        MODULE_KIND_COMPILED: importlib.machinery.SourcelessFileLoader,
        MODULE_KIND_EXTENSION: importlib.machinery.ExtensionFileLoader
    }
    # pylint: enable=no-member
else:
    SUFFIXES = imp.get_suffixes()

# Don't shadow built-ins
__func_alias__ = {
    'exec_': 'exec'
}


class _DynamicModule(object):
    def load(self, code):
        execdict = {'__builtins__': None}  # optional, to increase safety
        exec(code, execdict)
        keys = execdict.get(
            '__all__',  # use __all__ attribute if defined
            # else all non-private attributes
            (key for key in execdict if not key.startswith('_')))
        for key in keys:
            setattr(self, key, execdict[key])


def exec_(source=None, contents=None, entry=None, *args, **kwargs):
    '''
    Allow running python scripts from inside the salt environment

    source
        A file on the minion or in the salt fileserver to load.

    content
        A string to load as a module

    entry
        Function in the loaded module to execute and return the output of

    .. note::

        All other args and kwargs are passed to the function that is called.

    .. code-block:: yaml

        salt '*' python.exec source=salt://command.py entry=main arg1=whatever
        salt '*' python.exec content='def main():\n    print('Hello')\n' entry=main arg1=whatever
    '''
    kwargs = __utils__['args.clean_kwargs'](**kwargs)
    ret = None
    if source is not None:
        suffix_map = {}
        suffix_order = [u'']  # local list to determine precedence of extensions
                             # Prefer packages (directories) over modules (single files)!
        for (suffix, mode, kind) in SUFFIXES:
            suffix_map[suffix] = (suffix, mode, kind)
            suffix_order.append(suffix)
        if any(source.startswith(proto) for proto in ('salt://', 'http://', 'https://', 'swift://', 's3://')):
            filepath = __salt__['cp.cache_file'](source)
        elif source.startswith('/'):
            filepath = source
        tmpfile, suffix = os.path.splitext(filepath)
        filedir, filename = os.path.dirname(tmpfile), os.path.basename(tmpfile)
        sys.path.append(filedir)
        
        if USE_IMPORTLIB:
            # pylint: disable=no-member
            # Package directory, look for __init__
            loader_details = [
                (importlib.machinery.SourceFileLoader, importlib.machinery.SOURCE_SUFFIXES),
                (importlib.machinery.SourcelessFileLoader, importlib.machinery.BYTECODE_SUFFIXES),
                (importlib.machinery.ExtensionFileLoader, importlib.machinery.EXTENSION_SUFFIXES),
            ]
            file_finder = importlib.machinery.FileFinder(
                filedir,
                *loader_details
            )
            spec = file_finder.find_spec(filename)
            if spec is None:
                raise ImportError()
            module = spec.loader.load_module(filename)
        else:
            with open(filepath, 'r') as fh_:
                module = imp.load_module(filename, fh_, filepath, suffix_map[suffix])
    elif contents:
        module = _DynamicModule()
        module.load(contents)
    else:
        return 'Invalid Input: source or contents is required to be specified'
    if entry:
        ret = getattr(module, entry)(*args, **kwargs)
    return ret
