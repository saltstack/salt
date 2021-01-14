# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals, with_statement

import threading


class ClassProperty(property):
    """
    Use a classmethod as a property
    http://stackoverflow.com/a/1383402/1258307
    """

    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()  # pylint: disable=no-member


class RequestContext(object):
    """
    A context manager that saves some per-thread state globally.
    Intended for use with Tornado's StackContext.
    https://gist.github.com/simon-weber/7755289
    Simply import this class into any module and access the current request handler by this
    class's class method property 'current'. If it returns None, there's no active request.
    .. code:: python
        from raas.utils.ctx import RequestContext
        current_request_handler = RequestContext.current
    """

    _state = threading.local()
    _state.current_request = {}

    def __init__(self, current_request):
        self._current_request = current_request

    @ClassProperty
    @classmethod
    def current(cls):
        if not hasattr(cls._state, "current_request"):
            return {}
        return cls._state.current_request

    def __enter__(self):
        self._prev_request = self.__class__.current
        self.__class__._state.current_request = self._current_request

    def __exit__(self, *exc):
        self.__class__._state.current_request = self._prev_request
        del self._prev_request
        return False

    def __call__(self):
        return self
