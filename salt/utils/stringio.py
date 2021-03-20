"""
Functions for StringIO objects
"""


# Not using six's fake cStringIO since we need to be able to tell if the object
# is readable, and this can't be done via what six exposes.
import io

from salt.ext import six

readable_types = (io.StringIO,)
writable_types = (io.StringIO,)


def is_stringio(obj):
    return isinstance(obj, readable_types)


def is_readable(obj):
    return isinstance(obj, readable_types) and obj.readable()


def is_writable(obj):
    return isinstance(obj, writable_types) and obj.writable()
