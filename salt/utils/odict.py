# -*- coding: utf-8 -*-
'''
    salt.utils.odict
    ~~~~~~~~~~~~~~~~

    This is a compatibility/"importability" layer for an ordered dictionary.
    Tries to import from the standard library if python >= 2.7, then from the
    ``ordereddict`` package available from PyPi, and, as a last resort,
    provides an ``OrderedDict`` implementation based on::

        http://code.activestate.com/recipes/576669/

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

try:
    from collections import OrderedDict
except ImportError:
    try:
        from ordereddict import OrderedDict
    except ImportError:
        from collections import MutableMapping

        class OrderedDict(dict, MutableMapping):
            # This implementation is fully based on:
            #   http://code.activestate.com/recipes/576669/

            # Methods with direct access to underlying attributes
            def __init__(self, *args, **kwds):
                if len(args) > 1:
                    raise TypeError(
                        'expected at 1 argument, got %d', len(args)
                    )
                if not hasattr(self, '_keys'):
                    self._keys = []
                self.update(*args, **kwds)

            def clear(self):
                del self._keys[:]
                dict.clear(self)

            def __setitem__(self, key, value):
                if key not in self:
                    self._keys.append(key)
                dict.__setitem__(self, key, value)

            def __delitem__(self, key):
                dict.__delitem__(self, key)
                self._keys.remove(key)

            def __iter__(self):
                return iter(self._keys)

            def __reversed__(self):
                return reversed(self._keys)

            def popitem(self):
                if not self:
                    raise KeyError
                key = self._keys.pop()
                value = dict.pop(self, key)
                return key, value

            def __reduce__(self):
                items = [[k, self[k]] for k in self]
                inst_dict = vars(self).copy()
                inst_dict.pop('_keys', None)
                return (self.__class__, (items,), inst_dict)

            # Methods with indirect access via the above methods

            setdefault = MutableMapping.setdefault
            update = MutableMapping.update
            pop = MutableMapping.pop
            keys = MutableMapping.keys
            values = MutableMapping.values
            items = MutableMapping.items

            def __repr__(self):
                pairs = ', '.join(map('%r: %r'.__mod__, self.items()))
                return '%s({%s})' % (self.__class__.__name__, pairs)

            def copy(self):
                return self.__class__(self)

            @classmethod
            def fromkeys(cls, iterable, value=None):
                d = cls()
                for key in iterable:
                    d[key] = value
                return d
