# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :codeauthor: :email:`Thomas Jackson (jacksontj.89@gmail.com)`


    salt.utils.context
    ~~~~~~~~~~~~~~~~~~

    Context managers used throughout Salt's source code.
'''
from __future__ import absolute_import

# Import python libs
import copy
import threading
import collections
from contextlib import contextmanager

import salt.ext.six


@contextmanager
def func_globals_inject(func, **overrides):
    '''
    Override specific variables within a function's global context.
    '''
    # recognize methods
    if hasattr(func, 'im_func'):
        func = func.__func__

    # Get a reference to the function globals dictionary
    func_globals = func.__globals__
    # Save the current function globals dictionary state values for the
    # overridden objects
    injected_func_globals = []
    overridden_func_globals = {}
    for override in overrides:
        if override in func_globals:
            overridden_func_globals[override] = func_globals[override]
        else:
            injected_func_globals.append(override)

    # Override the function globals with what's passed in the above overrides
    func_globals.update(overrides)

    # The context is now ready to be used
    yield

    # We're now done with the context

    # Restore the overwritten function globals
    func_globals.update(overridden_func_globals)

    # Remove any entry injected in the function globals
    for injected in injected_func_globals:
        del func_globals[injected]


class ContextDict(collections.MutableMapping):
    '''
    A context manager that saves some per-thread state globally.
    Intended for use with Tornado's StackContext.

    Provide arbitrary data as kwargs upon creation,
    then allow any children to override the values of the parent.
    '''

    def __init__(self, **data):
        # state should be thread local, so this object can be threadsafe
        self._state = threading.local()
        # variable for the overriden data
        self._state.data = None
        self.global_data = {}

    @property
    def active(self):
        '''Determine if this ContextDict is currently overriden
        Since the ContextDict can be overriden in each thread, we check whether
        the _state.data is set or not.
        '''
        try:
            return self._state.data is not None
        except AttributeError:
            return False

    # TODO: rename?
    def clone(self, **kwargs):
        '''
        Clone this context, and return the ChildContextDict
        '''
        child = ChildContextDict(parent=self, overrides=kwargs)
        return child

    def __setitem__(self, key, val):
        if self.active:
            self._state.data[key] = val
        else:
            self.global_data[key] = val

    def __delitem__(self, key):
        if self.active:
            del self._state.data[key]
        else:
            del self.global_data[key]

    def __getitem__(self, key):
        if self.active:
            return self._state.data[key]
        else:
            return self.global_data[key]

    def __len__(self):
        if self.active:
            return len(self._state.data)
        else:
            return len(self.global_data)

    def __iter__(self):
        if self.active:
            return iter(self._state.data)
        else:
            return iter(self.global_data)


class ChildContextDict(collections.MutableMapping):
    '''An overrideable child of ContextDict

    '''
    def __init__(self, parent, overrides=None):
        self.parent = parent
        self._data = {} if overrides is None else overrides

        # merge self.global_data into self._data
        for k, v in self.parent.global_data.iteritems():
            if k not in self._data:
                self._data[k] = copy.deepcopy(v)

    def __setitem__(self, key, val):
        self._data[key] = val

    def __delitem__(self, key):
        del self._data[key]

    def __getitem__(self, key):
        return self._data[key]

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __enter__(self):
        self.parent._state.data = self._data

    def __exit__(self, *exc):
        self.parent._state.data = None


class NamespacedDictWrapper(collections.MutableMapping, dict):
    '''
    Create a dict which wraps another dict with a specific prefix of key(s)

    MUST inherit from dict to serialize through msgpack correctly
    '''
    def __init__(self, d, pre_keys):  # pylint: disable=W0231
        self.__dict = d
        if isinstance(pre_keys, salt.ext.six.string_types):
            self.pre_keys = (pre_keys,)
        else:
            self.pre_keys = pre_keys

    def _dict(self):
        r = self.__dict
        for k in self.pre_keys:
            r = r[k]
        return r

    def __setitem__(self, key, val):
        self._dict()[key] = val

    def __delitem__(self, key):
        del self._dict()[key]

    def __getitem__(self, key):
        return self._dict()[key]

    def __len__(self):
        return len(self._dict())

    def __iter__(self):
        return iter(self._dict())

    def __deepcopy__(self, memo):
        return type(self)(copy.deepcopy(self.__dict, memo),
                          copy.deepcopy(self.pre_keys, memo))
