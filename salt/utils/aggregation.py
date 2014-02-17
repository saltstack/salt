
from __future__ import absolute_import
from copy import copy
import logging

from salt.utils.odict import OrderedDict

__all__ = ['aggregate', 'Aggregate', 'Map', 'Scalar', 'Sequence']

log = logging.getLogger(__name__)


class Aggregate(object):
    pass


class Map(OrderedDict, Aggregate):
    pass


class Sequence(list, Aggregate):
    pass


def Scalar(obj):
    """
    Shortcut for Sequence creation

    >>> Scalar('foo') == Sequence(['foo'])
    True
    """
    return Sequence([obj])


def levelise(level):
    """
    Describe which levels are allowed to do deep merging.

    level can be:

    True
        all levels are True

    False
        all levels are False

    an int
        only the first levels are True, the others are False

    a sequence
        it describes which levels are True, it can be:

        * a list of bool and int values
        * a string of 0 and 1 characters

    """

    if not level:  # False, 0, [] ...
        return False, False
    if level is True:
        return True, True
    if isinstance(level, int):
        return True, level - 1
    try:  # a sequence
        deep, subs = int(level[0]), level[1:]
        return bool(deep), subs
    except Exception as error:
        log.warning(error)
        raise


def mark(obj, Map=Map, Sequence=Sequence):
    if isinstance(obj, Aggregate):
        return obj
    if isinstance(obj, dict):
        return Map(obj)
    if isinstance(obj, (list, tuple, set)):
        return Sequence(obj)
    else:
        return Sequence([obj])


def aggregate(a, b, level=False, Map=Map, Sequence=Sequence):  # NOQA
    """
    >>> aggregate('first', 'second', True) == ['first', 'second']
    True
    """
    deep, subdeep = levelise(level)

    if deep:
        a, b = mark(a), mark(b)

    specs = {
        'level': subdeep,
        'Map': Map,
        'Sequence': Sequence
    }

    if isinstance(a, dict) and isinstance(b, dict):
        if isinstance(a, Aggregate) and isinstance(b, Aggregate):
            # deep merging is more or less a.update(b)
            response = copy(a)
        else:
            # introspection on b keys only
            response = copy(b)

        for key, value in b.items():
            if key in a:
                value = aggregate(a[key], value, **specs)
            response[key] = value
        return response

    if isinstance(a, Sequence) and isinstance(a, Sequence):
        response = a.__class__(a[:])
        for value in b:
            if value not in a:
                response.append(value)
        return response

    if isinstance(a, Aggregate) or isinstance(a, Aggregate):
        log.info('only one value marked as aggregate. keep `a` value')
        return b

    log.debug('no value marked as aggregate. keep `a` value')
    return b
