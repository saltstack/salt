# -*- coding: utf-8 -*-
'''
salt.utils.singleton
~~~~~~~~~~~~~~~~~~~~

Borg Pattern Singleton implementation
'''

# Import Python libs
from __future__ import absolute_import
import gc
import atexit
import logging

# Import Salt libs
from salt._compat import weakref

log = logging.getLogger(__name__)


class BorgKeyedState(object):
    '''
    Class implementing the Borg singleton pattern, however, instead of all subclasses
    sharing the same state, we keep several states under different keys
    '''

    __state = {}
    __permanent_state_keys__ = ('_state_key', '_state_key_repr')

    def __init__(self, *args, **kwargs):
        state_key = self.__get_state_key__(*args, **kwargs)
        if state_key not in self.__state:
            self.__state[state_key] = {}
        self.__dict__ = self.__state[state_key]
        self._state_key = state_key
        self._state_key_repr = self.__get_state_key_repr__(*args, **kwargs)

    def __get_state_key__(self, *args, **kwargs):
        raise NotImplementedError

    def __get_state_key_repr__(self, *args, **kwargs):  # pylint: disable=unused-argument
        return 'for cache key \'{}\''.format(self._state_key)

    def __repr__(self):
        return '<{} {} at %#x>'.format(self.__class__.__name__, self._state_key_repr) % (id(self),)

    @classmethod
    def __reset_state__(cls, state, **new_state):
        for key in cls.__permanent_state_keys__:
            if key not in new_state:
                new_state[key] = state[key]

        for key in state:
            if key in new_state:
                continue
            new_state[key] = None
        return new_state

    @classmethod
    def __nuke_state__(cls, state_key):
        if state_key in cls.__state:
            log.warning('Deleting state key %r', state_key)
            del cls.__state[state_key]


class Singleton(BorgKeyedState):
    '''
    Singleton implementation which knows how to destroy itself when there are no more
    references to itself or on python interpreter shutdown(in case something holds a
    strong reference to it).
    '''

    __permanent_state_keys__ = BorgKeyedState.__permanent_state_keys__ + (
            '_singleton_instance', '_singleton_destroy')

    def __init__(self, *args, **kwargs):
        super(Singleton, self).__init__(*args, **kwargs)
        if '_singleton_instance' in self.__dict__:
            log.debug(
                'Reusing %s singleton %s',
                self.__class__.__name__,
                self._state_key_repr
            )
        else:
            log.debug(
                'Instantiating new %s singleton %s',
                self.__class__.__name__,
                self._state_key_repr
            )
            self.__singleton_init__(*args, **kwargs)
            self._singleton_instance = True
            self._singleton_destroy = False

        # The following finalize method gets passed a few objects and even functions(which need to either
        # be  a classmethod or a staticmethod) because passing a reference to the instance(self)  will
        # prevent/delay python's GC from running the finalize functions until the end of the python
        # interpreter. IE, it keeps a strong reference to the class instance.

        # Register finalize code for when the object is about to be GC
        self._finalizer = weakref.finalize(
            self,
            self.__singleton_destroy__,
            self.__class__,
            self._state_key,
            self._state_key_repr,
            self.__dict__,
            self.__singleton_deinit__,
        )

    def __singleton_init__(self, *args, **kwargs):
        raise NotImplementedError

    @staticmethod
    def __singleton_deinit__(state_dict):
        pass

    @staticmethod
    def __singleton_destroy__(klass,
                              state_key,
                              state_key_repr,
                              state_dict,
                              singleton_deinit_func):

        if state_dict['_singleton_destroy']:
            return

        # Compute a refcount. The number of class instances sharing the same state
        refcount = len([ref for ref in gc.get_referrers(state_dict) if isinstance(ref, klass)])
        log.debug(
            '%s.__singleton_destroy__() called %s. Refcount: %d',
            klass.__name__,
            state_key_repr,
            refcount,
        )

        if refcount > 1:
            # This is not the last reference to the borg state
            # Reset this instance's state
            state_dict.update(klass.__reset_state__(state_dict))
            # Don't run any destruction code just yet.
            return

        # By now this is the last reference, run any destruction code required
        state_dict['_singleton_destroy'] = True
        log.debug(
            'Calling %s.__singleton_deinit__() (%s) %s',
            klass.__name__,
            singleton_deinit_func,
            state_key_repr)
        singleton_deinit_func(state_dict)
        # Nuke the whole borg cache for this state key
        BorgKeyedState.__nuke_state__(state_key)
