# -*- coding: utf-8 -*-
'''
    salt.utils.aggregation
    ~~~~~~~~~~~~~~~~~~~~~~

    This library makes it possible to introspect dataset and aggregate nodes
    when it is instructed.

    .. note::

        The following examples with be expressed in YAML for convenience's sake:

        - !aggr-scalar will refer to Scalar python function
        - !aggr-map will refer to Map python object
        - !aggr-seq will refer for Sequence python object


    How to instructs merging
    ------------------------

    This yaml document has duplicate keys:

    .. code-block:: yaml

        foo: !aggr-scalar first
        foo: !aggr-scalar second
        bar: !aggr-map {first: foo}
        bar: !aggr-map {second: bar}
        baz: !aggr-scalar 42

    but tagged values instruct Salt that overlapping values they can be merged
    together:

    .. code-block:: yaml

        foo: !aggr-seq [first, second]
        bar: !aggr-map {first: foo, second: bar}
        baz: !aggr-seq [42]


    Default merge strategy is keep untouched
    ----------------------------------------

    For example, this yaml document still has duplicate keys, but does not
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

    TODO: write this part

'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import logging

# Import Salt libs
from salt.utils.odict import OrderedDict

# Import 3rd-party libs
from salt.ext import six

__all__ = ['aggregate', 'Aggregate', 'Map', 'Scalar', 'Sequence']

log = logging.getLogger(__name__)


class Aggregate(object):
    '''
    Aggregation base.
    '''


class Map(OrderedDict, Aggregate):
    '''
    Map aggregation.
    '''


class Sequence(list, Aggregate):
    '''
    Sequence aggregation.
    '''


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


def mark(obj, map_class=Map, sequence_class=Sequence):
    '''
    Convert obj into an Aggregate instance
    '''
    if isinstance(obj, Aggregate):
        return obj
    if isinstance(obj, dict):
        return map_class(obj)
    if isinstance(obj, (list, tuple, set)):
        return sequence_class(obj)
    else:
        return sequence_class([obj])


def aggregate(obj_a, obj_b, level=False, map_class=Map, sequence_class=Sequence):
    '''
    Merge obj_b into obj_a.

    >>> aggregate('first', 'second', True) == ['first', 'second']
    True
    '''
    deep, subdeep = levelise(level)

    if deep:
        obj_a = mark(obj_a, map_class=map_class, sequence_class=sequence_class)
        obj_b = mark(obj_b, map_class=map_class, sequence_class=sequence_class)

    if isinstance(obj_a, dict) and isinstance(obj_b, dict):
        if isinstance(obj_a, Aggregate) and isinstance(obj_b, Aggregate):
            # deep merging is more or less a.update(obj_b)
            response = copy.copy(obj_a)
        else:
            # introspection on obj_b keys only
            response = copy.copy(obj_b)

        for key, value in six.iteritems(obj_b):
            if key in obj_a:
                value = aggregate(obj_a[key], value,
                                  subdeep, map_class, sequence_class)
            response[key] = value
        return response

    if isinstance(obj_a, Sequence) and isinstance(obj_b, Sequence):
        response = obj_a.__class__(obj_a[:])
        for value in obj_b:
            if value not in obj_a:
                response.append(value)
        return response

    response = copy.copy(obj_b)

    if isinstance(obj_a, Aggregate) or isinstance(obj_b, Aggregate):
        log.info('only one value marked as aggregate. keep `obj_b` value')
        return response

    log.debug('no value marked as aggregate. keep `obj_b` value')
    return response
