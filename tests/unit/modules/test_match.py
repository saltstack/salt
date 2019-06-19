# -*- coding: utf-8 -*-
'''
    :codeauthor: Oleg Lipovchenko <oleg.lipovchenko@gmail.com>
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals


# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
)

# Import Salt Libs
from salt.exceptions import SaltException
import salt.modules.match as match
import salt.matchers.compound_match as compound_match
import salt.matchers.glob_match as glob_match

MATCHERS_DICT = {
    'compound_match.match': compound_match.match,
    'glob_match.match': glob_match.match
    }

# the name of the minion to be used for tests
MINION_ID = 'bar03'


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.loader.matchers', MagicMock(return_value=MATCHERS_DICT))
class MatchTestCase(TestCase, LoaderModuleMockMixin):
    '''
    This class contains a set of functions that test salt.modules.match.
    '''

    def setup_loader_modules(self):
        return {
            match: {
                '__opts__': {
                    'extension_modules': '',
                    'id': MINION_ID
                }
            },
            compound_match: {
                '__opts__': {
                    'id': MINION_ID
                }
            },
            glob_match: {
                '__opts__': {'id': MINION_ID}
            }
        }

    def test_filter_by(self):
        '''
        Tests if filter_by returns the correct dictionary.
        '''
        lookup = {
            'foo*': {
                'key1': 'fooval1', 'key2': 'fooval2'
            },
            'bar*': {
                'key1': 'barval1', 'key2': 'barval2'
            }
        }
        result = {'key1': 'barval1', 'key2': 'barval2'}

        self.assertDictEqual(match.filter_by(lookup), result)

    def test_filter_by_merge(self):
        '''
        Tests if filter_by returns a dictionary merged with another dictionary.
        '''
        lookup = {
            'foo*': {
                'key1': 'fooval1', 'key2': 'fooval2'
            },
            'bar*': {
                'key1': 'barval1', 'key2': 'barval2'
            }
        }
        mdict = {'key1': 'mergeval1'}
        result = {'key1': 'mergeval1', 'key2': 'barval2'}

        self.assertDictEqual(match.filter_by(lookup, merge=mdict), result)

    def test_filter_by_merge_lists_rep(self):
        '''
        Tests if filter_by merges list values by replacing the original list
        values with the merged list values.
        '''
        lookup = {
            'foo*': {
                'list_key': []
             },
            'bar*': {
                'list_key': [
                    'val1',
                    'val2'
                ]
            }
        }

        mdict = {
            'list_key': [
                'val3',
                'val4'
            ]
        }

        # list replacement specified by the merge_lists=False option
        result = {
            'list_key': [
                'val3',
                'val4'
            ]
        }

        self.assertDictEqual(match.filter_by(lookup, merge=mdict, merge_lists=False), result)

    def test_filter_by_merge_lists_agg(self):
        '''
        Tests if filter_by merges list values by aggregating them.
        '''
        lookup = {
            'foo*': {
                'list_key': []
             },
            'bar*': {
                'list_key': [
                    'val1',
                    'val2'
                ]
            }
        }

        mdict = {
            'list_key': [
                'val3',
                'val4'
            ]
        }

        # list aggregation specified by the merge_lists=True option
        result = {
            'list_key': [
                'val1',
                'val2',
                'val3',
                'val4'
            ]
        }

        self.assertDictEqual(match.filter_by(lookup, merge=mdict, merge_lists=True), result)

    def test_filter_by_merge_with_none(self):
        '''
        Tests if filter_by merges a None object with a merge dictionary.
        '''
        lookup = {
            'foo*': {
                'key1': 'fooval1', 'key2': 'fooval2'
            },
            'bar*': None
        }

        # mdict should also be the returned dictionary
        # since a merge is done with None
        mdict = {'key1': 'mergeval1'}

        self.assertDictEqual(match.filter_by(lookup, merge=mdict), mdict)

    def test_filter_by_merge_fail(self):
        '''
        Tests for an exception if a merge is done without a dictionary.
        '''
        lookup = {
            'foo*': {
                'key1': 'fooval1', 'key2': 'fooval2'
            },
            'bar*': {
                'key1': 'barval1', 'key2': 'barval2'
            }
        }
        mdict = 'notadict'

        self.assertRaises(
            SaltException,
            match.filter_by,
            lookup,
            merge=mdict
        )
