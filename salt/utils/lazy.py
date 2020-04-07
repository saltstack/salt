# -*- coding: utf-8 -*-
"""
Lazily-evaluated data structures, primarily used by Salt's loader
"""

# Import Python Libs
from __future__ import absolute_import, unicode_literals

import logging

import salt.exceptions

try:
    from collections.abc import MutableMapping
except ImportError:
    # pylint: disable=no-name-in-module
    from collections import MutableMapping

    # pylint: enable=no-name-in-module

log = logging.getLogger(__name__)


def verify_fun(lazy_obj, fun):
    """
    Check that the function passed really exists
    """
    if not fun:
        raise salt.exceptions.SaltInvocationError(
            "Must specify a function to run!\n" "ex: manage.up"
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
        return "'{0}' is not available.".format(function_name)

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
