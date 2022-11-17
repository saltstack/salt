"""
Lazily-evaluated data structures, primarily used by Salt's loader
"""


import importlib.util
import logging
import sys
from collections.abc import MutableMapping

import salt.exceptions

log = logging.getLogger(__name__)


def verify_fun(lazy_obj, fun):
    """
    Check that the function passed really exists
    """
    if not fun:
        raise salt.exceptions.SaltInvocationError(
            "Must specify a function to run!\nex: manage.up"
        )
    if fun not in lazy_obj:
        # If the requested function isn't available, lets say why
        raise salt.exceptions.CommandExecutionError(lazy_obj.missing_fun_string(fun))


class LazyDict(MutableMapping):
    """
    A base class of dict which will lazily load keys once they are needed

    TODO: negative caching? If you ask for 'foo' and it doesn't exist it will
    look EVERY time unless someone calls load_all()
    As of now this is left to the class which inherits from this base
    """

    def __init__(self):
        self.clear()

    def __nonzero__(self):
        # we are zero if dict is empty and loaded is true
        return bool(self._dict or not self.loaded)

    def __bool__(self):
        # we are zero if dict is empty and loaded is true
        return self.__nonzero__()

    def clear(self):
        """
        Clear the dict
        """
        # create a dict to store loaded values in
        self._dict = getattr(self, "mod_dict_class", dict)()

        # have we already loded everything?
        self.loaded = False

    def _load(self, key):
        """
        Load a single item if you have it
        """
        raise NotImplementedError()

    def _load_all(self):
        """
        Load all of them
        """
        raise NotImplementedError()

    def _missing(self, key):
        """
        Whether or not the key is missing (meaning we know it's not there)
        """
        return False

    def missing_fun_string(self, function_name):
        """
        Return the error string for a missing function.

        Override this to return a more meaningfull error message if possible
        """
        return "'{}' is not available.".format(function_name)

    def __setitem__(self, key, val):
        self._dict[key] = val

    def __delitem__(self, key):
        del self._dict[key]

    def __getitem__(self, key):
        """
        Check if the key is ttld out, then do the get
        """
        if self._missing(key):
            raise KeyError(key)

        if key not in self._dict and not self.loaded:
            # load the item
            if self._load(key):
                log.debug("LazyLoaded %s", key)
                return self._dict[key]
            else:
                log.debug(
                    "Could not LazyLoad %s: %s", key, self.missing_fun_string(key)
                )
                raise KeyError(key)
        else:
            return self._dict[key]

    def __len__(self):
        # if not loaded,
        if not self.loaded:
            self._load_all()
        return len(self._dict)

    def __iter__(self):
        if not self.loaded:
            self._load_all()
        return iter(self._dict)


class _LazyModuleLoader(importlib.util.LazyLoader):  # pylint: disable=abstract-method
    _known = {"__file__", "__loader__", "__name__", "__path__", "__spec__"}

    class _LazyModule(importlib.util._LazyModule):
        def __getattribute__(self, attr):
            # Avoid triggering load for attributes whose value is already known.
            # This makes it possible to lazy load a module without eagerly
            # loading its parent module.
            if attr in _LazyModuleLoader._known:
                grandself = super(importlib.util._LazyModule, self)
                return grandself.__getattribute__(attr)
            # If the parent module is a lazy module, load it first in case it
            # mutates this module during its load.
            parent_name = self.__name__.rpartition(".")[0]
            if parent_name:
                parent_mod = importlib.import_module(parent_name)
                if isinstance(parent_mod, _LazyModuleLoader._LazyModule):
                    # There is no risk of infinite recursion if the parent
                    # module accesses an attribute of this module during its
                    # load because the parent's module type is changed to
                    # types.ModuleType before it loads.
                    vars(parent_mod)
            # If the parent module accessed an attribute of this module while it
            # was loading, then this __getattribute__ method was called a second
            # time and returned before the first call reached this point.  In
            # that case, the second call will have already completed the load so
            # a plain getattr() should suffice.
            if not isinstance(self, _LazyModuleLoader._LazyModule):
                return getattr(self, attr)
            return super().__getattribute__(attr)

    def exec_module(self, module):
        super().exec_module(module)
        module.__class__ = self._LazyModule


def lazy_import(name):
    """Python ``import`` with loading delayed until first attribute access.

    This function is meant to be a drop-in replacement for the Python ``import``
    statement.  In other words, the following:

    .. code-block:: python

        import salt.utils.lazy
        _baz = salt.utils.lazy.lazy_import("foo.bar.baz")

    behaves the same as:

    .. code-block:: python

        import foo.bar.baz as _baz

    except the actual read of ``foo/__init__.py``, ``foo/bar/__init__.py``, and
    ``foo/bar/baz.py``—and the execution of their contents—does not happen until
    an attribute of ``_baz`` is read or deleted (assuming the modules are not
    already loaded).

    Lazily importing modules is useful for breaking circular imports or for
    improving startup speed.

    If the module is not a top-level module (in other words, if ``name``
    contains a period), the module's parent module is also imported lazily.

    Relative imports are not supported.

    Advantages of this function over a delayed ``import`` statement (an
    ``import`` statement inside a function instead of at the top of the ``.py``
    file):

    * This function immediately checks whether the module can be loaded without
      loading it, so an ``ImportError`` exception will be raised right away if
      the module is missing.
    * The statement ``import foo.bar`` anywhere in a function makes ``foo`` a
      function-local variable unless ``global foo`` is added to the function.
      This will cause references to ``foo`` to raise an "UnboundLocalError:
      local variable 'foo' referenced before assignment" exception unless the
      ``import`` statement is guaranteed to execute before any reference to
      ``foo``.

    Disadvantages vs. an ordinary ``import`` statement at the top of the file:

    * Added latency when the lazily imported module is first used.
    * Any exception raised during module load will surface when the lazily
      imported module is first used, not during program startup.

    This function is a copy of
    <https://docs.python.org/3.11/library/importlib.html#implementing-lazy-imports>
    with the following changes:

    * This version checks if the module has already been imported.
    * This version supports lazy loading of parent modules (the example given in
      the Python documentation always eagerly loads any parent modules).
    * When importing a module like ``parent.child``, the ``child`` attribute of
      the ``parent`` module is set to the ``parent.child`` module object (like
      the ``import`` statement does).

    """
    try:
        return sys.modules[name]
    except KeyError:
        pass
    parent_name, _, child_name = name.rpartition(".")
    # Lazy import the parent module before creating the child module to prevent
    # importlib.util.find_spec() from eagerly importing the parent.
    parent_module = lazy_import(parent_name) if parent_name else None
    spec = importlib.util.find_spec(name)
    loader = _LazyModuleLoader(spec.loader)
    spec.loader = loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    if parent_module is not None:
        # Setting an attribute on a lazy module will not cause the module to
        # load -- only getting or deleting an attribute does that.  This
        # attribute will be preserved when the parent is eventually loaded.
        setattr(parent_module, child_name, module)
    return module
