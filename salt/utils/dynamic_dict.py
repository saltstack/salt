"""
A dictionary with optionally dynamic values, used for dynamic configuration such
as file roots.
"""

import copy

__all__ = ["DynamicDict"]


class DynamicDict(dict):
    """
    A dictionary that can mix static and dynamic values.
    """

    def __init__(self, *args, **argv):
        self._func_dict = {}
        super().__init__(*args, **argv)

    def __getitem__(self, key):
        val = super().__getitem__(key)
        if key in self._func_dict:
            val = self._func_dict[key](val, dyn_dict=self, key=key)
        return val

    def __delitem__(self, key):
        if key in self._func_dict:
            del self._func_dict[key]
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

    def copy(self):
        new_dd = DynamicDict()
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
        rdd = DynamicDict()
        memo[id(self)] = rdd
        iteritems = getattr(self, "items")
        for key, value in iteritems():
            if key in self._func_dict:
                func = self._func_dict[key]
                data = super().__getitem__(key)
                rdd.add_dyn(key, func, data)
            else:
                rdd[key] = value
            rdd[copy.deepcopy(key, memo)] = copy.deepcopy(value, memo)

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
        if data is not None or key not in self:
            self[key] = data
