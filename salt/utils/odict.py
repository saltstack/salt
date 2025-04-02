"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    salt.utils.odict
    ~~~~~~~~~~~~~~~~

    Implements a DefaultOrderedDict Class that serves  as a
    combination of ``OrderedDict`` and ``defaultdict``
    It's source was submitted here::

        http://stackoverflow.com/questions/6190331/
"""

import copy
from collections import OrderedDict
from collections.abc import Callable


class DefaultOrderedDict(OrderedDict):
    """
    Dictionary that remembers insertion order
    """

    def __init__(self, default_factory=None, *a, **kw):
        if default_factory is not None and not isinstance(default_factory, Callable):
            raise TypeError("first argument must be callable")
        super().__init__(*a, **kw)
        self.default_factory = default_factory

    def __getitem__(self, key):
        try:
            return OrderedDict.__getitem__(self, key)
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

    def __deepcopy__(self):
        import copy

        return type(self)(self.default_factory, copy.deepcopy(self.items()))

    def __repr__(self, _repr_running={}):  # pylint: disable=W0102
        return "DefaultOrderedDict({}, {})".format(
            self.default_factory, super().__repr__()
        )


class HashableOrderedDict(OrderedDict):
    def __hash__(self):
        return id(self)
