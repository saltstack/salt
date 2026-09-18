"""
A dictionary with optionally dynamic values, used for dynamic configuration such
as file roots.
"""

import copy
import time

__all__ = ["DynamicDict"]

#: Default number of seconds a dynamic value is cached before being
#: re-evaluated. Callers (e.g. ``salt.config``) may override this per
#: instance via the ``ttl`` argument.
DEFAULT_TTL = 5.0


class DynamicDict(dict):
    """
    A dictionary that can mix static and dynamic values.
    """

    def __init__(self, *args, ttl=DEFAULT_TTL, **argv):
        self._func_dict = {}
        self._cache = {}
        self._ttl = ttl
        super().__init__(*args, **argv)

    def __getitem__(self, key):
        val = super().__getitem__(key)
        if key in self._func_dict:
            now = time.time()
            cached = self._cache.get(key)
            if self._ttl and cached is not None and (now - cached[1]) < self._ttl:
                return cached[0]
            val = self._func_dict[key](val, dyn_dict=self, key=key)
            self._cache[key] = (val, now)
        return val

    def __delitem__(self, key):
        if key in self._func_dict:
            del self._func_dict[key]
        self._cache.pop(key, None)
        super().__delitem__(key)

    def get(self, key, default=None):
        if key not in self:
            return default
        return self[key]

    def pop(self, key, default=None):
        if key in self:
            val = self[key]
            del self[key]
        else:
            val = default
        return val

    def values(self):
        keys = super().keys()
        for key in keys:
            yield self[key]

    def items(self):
        keys = super().keys()
        for key in keys:
            yield key, self[key]

    def copy(self):
        new_dd = DynamicDict(ttl=self._ttl)
        for key, val in super().items():
            if key in self._func_dict:
                func = self._func_dict[key]
                data = super().__getitem__(key)
                new_dd.add_dyn(key, func, data)
            else:
                new_dd[key] = val
        return new_dd

    def __copy__(self):
        return self.copy()

    def __deepcopy__(self, memo):
        rdd = DynamicDict(ttl=self._ttl)
        memo[id(self)] = rdd
        for key in super().keys():
            if key in self._func_dict:
                func = self._func_dict[key]
                data = copy.deepcopy(super().__getitem__(key), memo)
                rdd.add_dyn(key, func, data)
            else:
                copied_key = copy.deepcopy(key, memo)
                copied_value = copy.deepcopy(super().__getitem__(key), memo)
                rdd[copied_key] = copied_value
        return rdd

    def static_dict(self):
        new_dict = {}
        for key in super().keys():
            new_dict[key] = self[key]
        return new_dict

    def is_dyn_key(self, key):
        return key in self._func_dict

    def add_dyn(self, key, func, data=None):
        if not hasattr(func, "__call__"):
            raise ValueError(f"Value for key '{key}' is not a function")
        self._func_dict[key] = func
        self._cache.pop(key, None)
        if data is not None or key not in self:
            self[key] = data
