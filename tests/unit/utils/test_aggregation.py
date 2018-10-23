# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import salt libs
from salt.utils.aggregation import aggregate, Map, Scalar


class TestAggregation(TestCase):
    def test_merging(self):
        a = {
            'foo': 42,
            'bar': 'first'
        }
        b = {
            'bar': 'second'
        }

        c, d = 'first', 'second'

        # introspection
        for level in (None, False, 0, []):
            assert aggregate(a, b, level=level) == {
                'bar': 'second'
            }
            assert aggregate(c, d, level=level) == 'second'

        # first level aggregation
        for level in (1, [1, 0], [True], '10000'):
            assert aggregate(a, b, level=level) == {
                'foo': 42,
                'bar': 'second'
            }
            assert aggregate(c, d, level=level) == ['first', 'second']

        # 1-2nd level aggregation
        for level in (2, [1, 1], [True, True], '11'):
            assert aggregate(a, b, level=level) == {
                'foo': 42,
                'bar': ['first', 'second']
            }, aggregate(a, b, level=2)
            assert aggregate(c, d, level=level) == ['first', 'second']

        # full aggregation
        for level in (True,):
            assert aggregate(a, b, level=level) == {
                'foo': 42,
                'bar': ['first', 'second']
            }
            assert aggregate(c, d, level=level) == ['first', 'second']

    def test_nested(self):
        a = {
            'foo': {
                'bar': 'first'
            }
        }
        b = {
            'foo': {
                'bar': 'second'
            }
        }
        assert aggregate(a, b) == {
            'foo': {
                'bar': 'second'
            }
        }, aggregate(a, b)

        a = {
            'foo': {
                'bar': Scalar('first')
            }
        }
        b = {
            'foo': {
                'bar': Scalar('second'),
            }
        }

        assert aggregate(a, b) == {
            'foo': {
                'bar': ['first', 'second']
            }
        }, aggregate(a, b)

    def test_introspection(self):

        a = {
            'foo': {
                'lvl1': {
                    'lvl2-a': 'first',
                    'lvl2-b': 'first'
                }
            }
        }

        b = {
            'foo': {
                'lvl1': {
                    'lvl2-a': 'second'
                }
            }
        }

        assert aggregate(a, b) == {
            'foo': {
                'lvl1': {
                    'lvl2-a': 'second'
                }
            }
        }, aggregate(a, b)

    def test_instruction(self):
        a = {
            'foo': Map({
                'bar': Scalar('first')
            })
        }
        b = {
            'foo': Map({
                'bar': Scalar('second')
            })
        }
        c = {
            'foo': Map({
                'another': 'value'
            })
        }
        result = aggregate(c, aggregate(a, b), level=2)
        assert result == {
            'foo': {
                'bar': ['first', 'second'],
                'another': 'value'
            }
        }, result
