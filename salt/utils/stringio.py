"""
Functions for StringIO objects
"""


import io

readable_types = (io.StringIO,)
writable_types = (io.StringIO,)


def is_stringio(obj):
    return isinstance(obj, readable_types)


def is_readable(obj):
    return isinstance(obj, readable_types) and obj.readable()


def is_writable(obj):
    return isinstance(obj, writable_types) and obj.writable()
