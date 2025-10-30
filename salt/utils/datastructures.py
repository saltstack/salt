"""
Utilities for working with ordered dictionary structures.

.. versionadded:: 300.0.0
"""

import copy
from collections import OrderedDict
from collections.abc import Callable

__all__ = ["DefaultOrderedDict", "HashableOrderedDict"]


class DefaultOrderedDict(OrderedDict):
    """
    An ordered dictionary with a default factory for missing keys.
    """

    def __init__(self, default_factory=None, *args, **kwargs):
        if default_factory is not None and not isinstance(default_factory, Callable):
            raise TypeError("first argument must be callable")
        super().__init__(*args, **kwargs)
        self.default_factory = default_factory

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            return self.__missing__(key)

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        self[key] = value = self.default_factory()
        return value

    def __reduce__(self):
        if self.default_factory is None:
            args = tuple()
        else:
            args = (self.default_factory,)
        return type(self), args, None, None, self.items()

    def copy(self):
        return copy.copy(self)

    def __copy__(self):
        return type(self)(self.default_factory, self)

    def __deepcopy__(self, memo):
        return type(self)(
            self.default_factory,
            copy.deepcopy(list(self.items()), memo),
        )

    def __repr__(self, _repr_running={}):  # pylint: disable=dangerous-default-value
        return f"DefaultOrderedDict({self.default_factory}, {super().__repr__()})"


class HashableOrderedDict(OrderedDict):
    """
    OrderedDict variant with a stable hash based on identity.
    """

    def __hash__(self):
        return id(self)
