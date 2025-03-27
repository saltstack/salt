"""
Manage the context a module loaded by Salt's loader
"""

import collections.abc
import contextlib
import copy

try:
    # Try the stdlib C extension first
    import _contextvars as contextvars
except ImportError:
    # Py<3.7
    import contextvars

import salt.exceptions

DEFAULT_CTX_VAR = "loader_ctxvar"

loader_ctxvar = contextvars.ContextVar(DEFAULT_CTX_VAR)


@contextlib.contextmanager
def loader_context(loader):
    """
    A context manager that sets and un-sets the loader context
    """
    tok = loader_ctxvar.set(loader)
    try:
        yield
    finally:
        loader_ctxvar.reset(tok)


class NamedLoaderContext(collections.abc.MutableMapping):
    """
    A NamedLoaderContext object is injected by the loader providing access to
    Salt's 'magic dunders' (__salt__, __utils__, etc).
    """

    def __init__(self, name, loader_context, default=None):
        self.name = name
        self.loader_context = loader_context
        self.default = default

    def with_default(self, default):
        return NamedLoaderContext(self.name, self.loader_context, default=default)

    def loader(self):
        """
        The LazyLoader in the current context. This will return None if there
        is no context established.
        """
        try:
            return self.loader_context.loader()
        except AttributeError:
            return None

    def eldest_loader(self):
        if self.loader() is None:
            return None
        loader = self.loader()
        while loader.parent_loader is not None:
            loader = loader.parent_loader
        return loader

    def value(self):
        """
        The value of the current for this context
        """
        loader = self.loader()
        if loader is None:
            return self.default
        if self.name == loader.pack_self:
            return loader
        elif self.name == "__context__":
            return loader.pack[self.name]
        elif self.name == "__opts__":
            return loader.pack[self.name]
        try:
            return loader.pack[self.name]
        except KeyError:
            raise salt.exceptions.LoaderError(
                f"LazyLoader does not have a packed value for: {self.name}"
            )

    def get(self, key, default=None):
        return self.value().get(key, default)

    def __getitem__(self, item):
        return self.value()[item]

    def __contains__(self, item):
        return item in self.value()

    def __setitem__(self, item, value):
        self.value()[item] = value

    def __bool__(self):
        return bool(self.value())

    def __len__(self):
        return self.value().__len__()

    def __iter__(self):
        return self.value().__iter__()

    def __delitem__(self, item):
        return self.value().__delitem__(item)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.loader_context == other.loader_context and self.name == other.name

    def __getstate__(self):
        return {
            "name": self.name,
            "loader_context": self.loader_context,
            "default": None,
        }

    def __setstate__(self, state):
        self.name = state["name"]
        self.loader_context = state["loader_context"]
        self.default = state["default"]

    def __getattr__(self, name):
        return getattr(self.value(), name)

    def __deepcopy__(self, memo):
        default = copy.deepcopy(self.default)
        return self.__class__(self.name, self.loader_context, default)

    def missing_fun_string(self, name):
        return self.loader().missing_fun_string(name)


class LoaderContext:
    """
    A loader context object, this object is injected at <loaded
    module>.__salt_loader__ by the Salt loader. It is responsible for providing
    access to the current context's loader
    """

    def __init__(self, loader_ctxvar=loader_ctxvar):
        self.loader_ctxvar = loader_ctxvar

    def __getitem__(self, item):
        return self.loader[item]

    def loader(self):
        """
        Return the LazyLoader in the current context. If there is no value set raise an AttributeError
        """
        try:
            return self.loader_ctxvar.get()
        except LookupError:
            raise AttributeError("No loader context")

    def named_context(self, name, default=None, ctx_class=NamedLoaderContext):
        """
        Return a NamedLoaderContext instance which will use this LoaderContext
        """
        return ctx_class(name, self, default)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.loader_ctxvar == other.loader_ctxvar

    def __getstate__(self):
        return {"varname": self.loader_ctxvar.name}

    def __setstate__(self, state):
        self.loader_ctxvar = contextvars.ContextVar(state["varname"])
