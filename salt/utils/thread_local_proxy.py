# -*- coding: utf-8 -*-
'''
Proxy object that can reference different values depending on the current
thread of execution.

..versionadded:: Neon

'''

# Import python libs
from __future__ import absolute_import
import threading

# Import 3rd-party libs
from salt.ext import six


class ThreadLocalProxy(object):
    '''
    Proxy that delegates all operations to its referenced object. The referenced
    object is hold through a thread-local variable, so that this proxy may refer
    to different objects in different threads of execution.

    For all practical purposes (operators, attributes, `isinstance`), the proxy
    acts like the referenced object. Thus, code receiving the proxy object
    instead of the reference object typically does not have to be changed. The
    only exception is code that explicitly uses the ``type()`` function for
    checking the proxy's type. While `isinstance(proxy, ...)` will yield the
    expected results (based on the actual type of the referenced object), using
    something like ``issubclass(type(proxy), ...)`` will not work, because
    these tests will be made on the type of the proxy object instead of the
    type of the referenced object. In order to avoid this, such code must be
    changed to use ``issubclass(type(ThreadLocalProxy.unproxy(proxy)), ...)``.

    If an instance of this class is created with the ``fallback_to_shared`` flag
    set and a thread uses the instance without setting the reference explicitly,
    the reference for this thread is initialized with the latest reference set
    by any thread.

    This class has primarily been designed for use by the Salt loader, but it
    might also be useful in other places.
    '''

    __slots__ = ['_thread_local', '_last_reference', '_fallback_to_shared']

    @staticmethod
    def get_reference(proxy):
        '''
        Return the object that is referenced by the specified proxy.

        If the proxy has not been bound to a reference for the current thread,
        the behavior depends on th the ``fallback_to_shared`` flag that has
        been specified when creating the proxy. If the flag has been set, the
        last reference that has been set by any thread is returned (and
        silently set as the reference for the current thread). If the flag has
        not been set, an ``AttributeError`` is raised.

        If the object references by this proxy is itself a proxy, that proxy is
        returned. Use ``unproxy`` for unwrapping the referenced object until it
        is not a proxy.

        proxy:
            proxy object for which the reference shall be returned. If the
            specified object is not an instance of `ThreadLocalProxy`, the
            behavior is unspecified. Typically, an ``AttributeError`` is
            going to be raised.
        '''
        thread_local = object.__getattribute__(proxy, '_thread_local')
        try:
            return thread_local.reference
        except AttributeError:
            fallback_to_shared = object.__getattribute__(
                proxy, '_fallback_to_shared')
            if fallback_to_shared:
                # If the reference has never been set in the current thread of
                # execution, we use the reference that has been last set by any
                # thread.
                reference = object.__getattribute__(proxy, '_last_reference')
                # We save the reference in the thread local so that future
                # calls to get_reference will have consistent results.
                ThreadLocalProxy.set_reference(proxy, reference)
                return reference
            else:
                # We could simply return None, but this would make it hard to
                # debug situations where the reference has not been set (the
                # problem might go unnoticed until some code tries to do
                # something with the returned object and it might not be easy to
                # find out from where the None value originates).
                # For this reason, we raise an AttributeError with an error
                # message explaining the problem.
                raise AttributeError(
                    'The proxy object has not been bound to a reference in this thread of execution.')

    @staticmethod
    def set_reference(proxy, new_reference):
        '''
        Set the reference to be used the current thread of execution.

        After calling this function, the specified proxy will act like it was
        the referenced object.

        proxy:
            proxy object for which the reference shall be set. If the specified
            object is not an instance of `ThreadLocalProxy`, the behavior is
            unspecified. Typically, an ``AttributeError`` is going to be
            raised.

        new_reference:
            reference the proxy should point to for the current thread after
            calling this function.
        '''
        # If the new reference is itself a proxy, we have to ensure that it does
        # not refer to this proxy. If it does, we simply return because updating
        # the reference would result in an inifite loop when trying to use the
        # proxy.
        possible_proxy = new_reference
        while isinstance(possible_proxy, ThreadLocalProxy):
            if possible_proxy is proxy:
                return
            possible_proxy = ThreadLocalProxy.get_reference(possible_proxy)
        thread_local = object.__getattribute__(proxy, '_thread_local')
        thread_local.reference = new_reference
        object.__setattr__(proxy, '_last_reference', new_reference)

    @staticmethod
    def unset_reference(proxy):
        '''
        Unset the reference to be used by the current thread of execution.

        After calling this function, the specified proxy will act like the
        reference had never been set for the current thread.

        proxy:
            proxy object for which the reference shall be unset. If the
            specified object is not an instance of `ThreadLocalProxy`, the
            behavior is unspecified. Typically, an ``AttributeError`` is going
            to be raised.
        '''
        thread_local = object.__getattribute__(proxy, '_thread_local')
        del thread_local.reference

    @staticmethod
    def unproxy(possible_proxy):
        '''
        Unwrap and return the object referenced by a proxy.

        This function is very similar to :func:`get_reference`, but works for
        both proxies and regular objects. If the specified object is a proxy,
        its reference is extracted with ``get_reference`` and returned. If it
        is not a proxy, it is returned as is.

        If the object references by the proxy is itself a proxy, the unwrapping
        is repeated until a regular (non-proxy) object is found.

        possible_proxy:
            object that might or might not be a proxy.
        '''
        while isinstance(possible_proxy, ThreadLocalProxy):
            possible_proxy = ThreadLocalProxy.get_reference(possible_proxy)
        return possible_proxy

    def __init__(self, initial_reference, fallback_to_shared=False):
        '''
        Create a proxy object that references the specified object.

        initial_reference:
            object this proxy should initially reference (for the current
            thread of execution). The :func:`set_reference` function is called
            for the newly created proxy, passing this object.

        fallback_to_shared:
            flag indicating what should happen when the proxy is used in a
            thread where the reference has not been set explicitly. If
            ``True``, the thread's reference is silently initialized to use the
            reference last set by any thread. If ``False`` (the default), an
            exception is raised when the proxy is used in a thread without
            first initializing the reference in this thread.
        '''
        object.__setattr__(self, '_thread_local', threading.local())
        object.__setattr__(self, '_fallback_to_shared', fallback_to_shared)
        ThreadLocalProxy.set_reference(self, initial_reference)

    def __repr__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return repr(reference)

    def __str__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return str(reference)

    def __lt__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference < other

    def __le__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference <= other

    def __eq__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference == other

    def __ne__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference != other

    def __gt__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference > other

    def __ge__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference >= other

    def __hash__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return hash(reference)

    def __nonzero__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return bool(reference)

    def __getattr__(self, name):
        reference = ThreadLocalProxy.get_reference(self)
        # Old-style classes might not have a __getattr__ method, but using
        # getattr(...) will still work.
        try:
            original_method = reference.__getattr__
        except AttributeError:
            return getattr(reference, name)
        return reference.__getattr__(name)

    def __setattr__(self, name, value):
        reference = ThreadLocalProxy.get_reference(self)
        reference.__setattr__(name, value)

    def __delattr__(self, name):
        reference = ThreadLocalProxy.get_reference(self)
        reference.__delattr__(name)

    def __getattribute__(self, name):
        reference = ThreadLocalProxy.get_reference(self)
        return reference.__getattribute__(name)

    def __call__(self, *args, **kwargs):
        reference = ThreadLocalProxy.get_reference(self)
        return reference(*args, **kwargs)

    def __len__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return len(reference)

    def __getitem__(self, key):
        reference = ThreadLocalProxy.get_reference(self)
        return reference[key]

    def __setitem__(self, key, value):
        reference = ThreadLocalProxy.get_reference(self)
        reference[key] = value

    def __delitem__(self, key):
        reference = ThreadLocalProxy.get_reference(self)
        del reference[key]

    def __iter__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return reference.__iter__()

    def __reversed__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return reversed(reference)

    def __contains__(self, item):
        reference = ThreadLocalProxy.get_reference(self)
        return item in reference

    def __add__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference + other

    def __sub__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference - other

    def __mul__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference * other

    def __floordiv__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference // other

    def __mod__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference % other

    def __divmod__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return divmod(reference, other)

    def __pow__(self, other, modulo=None):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        modulo = ThreadLocalProxy.unproxy(modulo)
        if modulo is None:
            return pow(reference, other)
        else:
            return pow(reference, other, modulo)

    def __lshift__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference << other

    def __rshift__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference >> other

    def __and__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference & other

    def __xor__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference ^ other

    def __or__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return reference | other

    def __div__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        try:
            func = reference.__div__
        except AttributeError:
            return NotImplemented
        return func(other)

    def __truediv__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        try:
            func = reference.__truediv__
        except AttributeError:
            return NotImplemented
        return func(other)

    def __radd__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return other + reference

    def __rsub__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return other - reference

    def __rmul__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return other * reference

    def __rdiv__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        try:
            func = reference.__rdiv__
        except AttributeError:
            return NotImplemented
        return func(other)

    def __rtruediv__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        try:
            func = reference.__rtruediv__
        except AttributeError:
            return NotImplemented
        return func(other)

    def __rfloordiv__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return other // reference

    def __rmod__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return other % reference

    def __rdivmod__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return divmod(other, reference)

    def __rpow__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return other ** reference

    def __rlshift__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return other << reference

    def __rrshift__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return other >> reference

    def __rand__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return other & reference

    def __rxor__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return other ^ reference

    def __ror__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return other | reference

    def __iadd__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        reference += other
        ThreadLocalProxy.set_reference(self, reference)
        return reference

    def __isub__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        reference -= other
        ThreadLocalProxy.set_reference(self, reference)
        return reference

    def __imul__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        reference *= other
        ThreadLocalProxy.set_reference(self, reference)
        return reference

    def __idiv__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        try:
            func = reference.__idiv__
        except AttributeError:
            return NotImplemented
        reference = func(other)
        ThreadLocalProxy.set_reference(self, reference)
        return reference

    def __itruediv__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        try:
            func = reference.__itruediv__
        except AttributeError:
            return NotImplemented
        reference = func(other)
        ThreadLocalProxy.set_reference(self, reference)
        return reference

    def __ifloordiv__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        reference //= other
        ThreadLocalProxy.set_reference(self, reference)
        return reference

    def __imod__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        reference %= other
        ThreadLocalProxy.set_reference(self, reference)
        return reference

    def __ipow__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        reference **= other
        ThreadLocalProxy.set_reference(self, reference)
        return reference

    def __ilshift__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        reference <<= other
        ThreadLocalProxy.set_reference(self, reference)
        return reference

    def __irshift__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        reference >>= other
        ThreadLocalProxy.set_reference(self, reference)
        return reference

    def __iand__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        reference &= other
        ThreadLocalProxy.set_reference(self, reference)
        return reference

    def __ixor__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        reference ^= other
        ThreadLocalProxy.set_reference(self, reference)
        return reference

    def __ior__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        reference |= other
        ThreadLocalProxy.set_reference(self, reference)
        return reference

    def __neg__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return - reference

    def __pos__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return + reference

    def __abs__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return abs(reference)

    def __invert__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return ~ reference

    def __complex__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return complex(reference)

    def __int__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return int(reference)

    def __float__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return float(reference)

    def __oct__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return oct(reference)

    def __hex__(self):
        reference = ThreadLocalProxy.get_reference(self)
        return hex(reference)

    def __index__(self):
        reference = ThreadLocalProxy.get_reference(self)
        try:
            func = reference.__index__
        except AttributeError:
            return NotImplemented
        return func()

    def __coerce__(self, other):
        reference = ThreadLocalProxy.get_reference(self)
        other = ThreadLocalProxy.unproxy(other)
        return coerce(reference, other)

    if six.PY2:
        # pylint: disable=incompatible-py3-code
        def __unicode__(self):
            reference = ThreadLocalProxy.get_reference(self)
            return unicode(reference)

        def __long__(self):
            reference = ThreadLocalProxy.get_reference(self)
            return long(reference)
