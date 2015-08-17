# -*- coding: utf-8 -*-
'''
    salt.serializers
    ~~~~~~~~~~~~~~~~~~~~~~

    This module implements all the serializers needed by salt.
    Each serializer offers the same functions and attributes:

    :deserialize: function for deserializing string or stream

    :serialize: function for serializing a Python object

    :available: flag that tells if the serializer is available
                (all dependencies are met etc.)

'''

from __future__ import absolute_import
from salt.exceptions import SaltException, SaltRenderError


class DeserializationError(SaltRenderError, RuntimeError):
    """Raised when stream of string failed to be deserialized"""
    pass


class SerializationError(SaltException, RuntimeError):
    """Raised when stream of string failed to be serialized"""
    pass
