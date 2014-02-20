# -*- coding: utf-8 -*-
'''
    salt.utils.aggregation
    ~~~~~~~~~~~~~~~~~~~~~~

    This library allows to introspect dataset and aggregate nodes when it is
    instructed.

    .. note::

        The following examples with be expressed in YAML for convenience sake:

        - !aggr-scalar will refer to Scalar python function
        - !aggr-map will refer to Map python object
        - !aggr-seq will refer for Sequence python object


    How to instructs merging
    ------------------------

    This yaml document have duplicate keys:

    .. code-block:: yaml

        foo: !aggr-scalar first
        foo: !aggr-scalar second
        bar: !aggr-map {first: foo}
        bar: !aggr-map {second: bar}
        baz: !aggr-scalar 42

    but tagged values instruct salt that overlaping values they can be merged
    together:

    .. code-block:: yaml

        foo: !aggr-seq [first, second]
        bar: !aggr-map {first: foo, second: bar}
        baz: !aggr-seq [42]


    Default merge strategy is keeped untouched
    ------------------------------------------

    For example, this yaml document have still duplicate keys, but does not
    instruct aggregation:

    .. code-block:: yaml

        foo: first
        foo: second
        bar: {first: foo}
        bar: {second: bar}
        baz: 42

    So the late found values prevail:

    .. code-block:: yaml

        foo: second
        bar: {second: bar}
        baz: 42


    Limitations
    -----------

    Aggregation is permitted between tagged objects that share the same type.
    If not, the default merge strategy prevails.

    For example, these examples:

    .. code-block:: yaml

        foo: {first: value}
        foo: !aggr-map {second: value}

        bar: !aggr-map {first: value}
        bar: 42

        baz: !aggr-seq [42]
        baz: [fail]

        qux: 42
        qux: !aggr-scalar fail

    are interpreted like this:

    .. code-block:: yaml

        foo: !aggr-map{second: value}

        bar: 42

        baz: [fail]

        qux: !aggr-seq [fail]


    Introspection
    -------------

    .. todo:: write this part

'''

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
    '''
    Shortcut for Sequence creation

    >>> Scalar('foo') == Sequence(['foo'])
    True
    '''
    return Sequence([obj])


def levelise(level):
    '''
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

    '''

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
    '''
    Merge b into a.

    >>> aggregate('first', 'second', True) == ['first', 'second']
    True
    '''
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
