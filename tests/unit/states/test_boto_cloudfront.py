# -*- coding: utf-8 -*-
'''
Unit tests for the boto_cloudfront state module.
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import textwrap

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import Salt Libs
import salt.config
import salt.loader
import salt.states.boto_cloudfront as boto_cloudfront


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoCloudfrontTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.boto_cloudfront
    '''
    def setup_loader_modules(self):
        utils = salt.loader.utils(
            self.opts,
            whitelist=['boto3', 'dictdiffer', 'yamldumper'],
            context={},
        )
        # Force the LazyDict to populate its references. Otherwise the lookup
        # will fail inside the unit tests.
        list(utils)
        return {
            boto_cloudfront: {
                '__utils__': utils,
            }
        }

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.DEFAULT_MINION_OPTS

        cls.name = 'my_distribution'
        cls.base_ret = {'name': cls.name, 'changes': {}}

        # Most attributes elided since there are so many required ones
        cls.config = {'Enabled': True, 'HttpVersion': 'http2'}
        cls.tags = {'test_tag1': 'value1'}

    @classmethod
    def tearDownClass(cls):
        del cls.opts

        del cls.name
        del cls.base_ret

        del cls.config
        del cls.tags

    def base_ret_with(self, extra_ret):
        new_ret = copy.deepcopy(self.base_ret)
        new_ret.update(extra_ret)
        return new_ret

    def test_present_distribution_retrieval_error(self):
        '''
        Test for boto_cloudfront.present when we cannot get the distribution.
        '''
        mock_get = MagicMock(return_value={'error': 'get_distribution error'})
        with patch.multiple(boto_cloudfront,
            __salt__={'boto_cloudfront.get_distribution': mock_get},
            __opts__={'test': False},
        ):
            comment = 'Error checking distribution {0}: get_distribution error'
            self.assertDictEqual(
                boto_cloudfront.present(self.name, self.config, self.tags),
                self.base_ret_with({
                    'result': False,
                    'comment': comment.format(self.name),
                }),
            )

    def test_present_from_scratch(self):
        mock_get = MagicMock(return_value={'result': None})

        with patch.multiple(boto_cloudfront,
            __salt__={'boto_cloudfront.get_distribution': mock_get},
            __opts__={'test': True},
        ):
            comment = 'Distribution {0} set for creation.'.format(self.name)
            self.assertDictEqual(
                boto_cloudfront.present(self.name, self.config, self.tags),
                self.base_ret_with({
                    'result': None,
                    'comment': comment,
                    'pchanges': {'old': None, 'new': self.name},
                }),
            )

        mock_create_failure = MagicMock(return_value={'error': 'create error'})
        with patch.multiple(boto_cloudfront,
            __salt__={
                'boto_cloudfront.get_distribution': mock_get,
                'boto_cloudfront.create_distribution': mock_create_failure,
            },
            __opts__={'test': False},
        ):
            comment = 'Error creating distribution {0}: create error'
            self.assertDictEqual(
                boto_cloudfront.present(self.name, self.config, self.tags),
                self.base_ret_with({
                    'result': False,
                    'comment': comment.format(self.name),
                }),
            )

        mock_create_success = MagicMock(return_value={'result': True})
        with patch.multiple(boto_cloudfront,
            __salt__={
                'boto_cloudfront.get_distribution': mock_get,
                'boto_cloudfront.create_distribution': mock_create_success,
            },
            __opts__={'test': False},
        ):
            comment = 'Created distribution {0}.'
            self.assertDictEqual(
                boto_cloudfront.present(self.name, self.config, self.tags),
                self.base_ret_with({
                    'result': True,
                    'comment': comment.format(self.name),
                    'changes': {'old': None, 'new': self.name},
                }),
            )

    def test_present_correct_state(self):
        mock_get = MagicMock(return_value={'result': {
            'distribution': {'DistributionConfig': self.config},
            'tags': self.tags,
            'etag': 'test etag',
        }})
        with patch.multiple(boto_cloudfront,
            __salt__={'boto_cloudfront.get_distribution': mock_get},
            __opts__={'test': False},
        ):
            comment = 'Distribution {0} has correct config.'
            self.assertDictEqual(
                boto_cloudfront.present(self.name, self.config, self.tags),
                self.base_ret_with({
                    'result': True,
                    'comment': comment.format(self.name),
                }),
            )

    def test_present_update_config_and_tags(self):
        mock_get = MagicMock(return_value={'result': {
            'distribution': {'DistributionConfig': {
                'Enabled': False,
                'Comment': 'to be removed',
            }},
            'tags': {'bad existing tag': 'also to be removed'},
            'etag': 'test etag',
        }})

        diff = textwrap.dedent('''\
            ---
            +++
            @@ -1,5 +1,5 @@
             config:
            -  Comment: to be removed
            -  Enabled: false
            +  Enabled: true
            +  HttpVersion: http2
             tags:
            -  bad existing tag: also to be removed
            +  test_tag1: value1

        ''').splitlines()
        # Difflib adds a trailing space after the +++/--- lines,
        # programatically add them back here. Having them in the test file
        # itself is not feasible since a few popular plugins for vim will
        # remove trailing whitespace.
        for idx in (0, 1):
            diff[idx] += ' '
        diff = '\n'.join(diff)

        with patch.multiple(boto_cloudfront,
            __salt__={'boto_cloudfront.get_distribution': mock_get},
            __opts__={'test': True},
        ):
            header = 'Distribution {0} set for new config:'.format(self.name)
            self.assertDictEqual(
                boto_cloudfront.present(self.name, self.config, self.tags),
                self.base_ret_with({
                    'result': None,
                    'comment': '\n'.join([header, diff]),
                    'pchanges': {'diff': diff},
                }),
            )

        mock_update_failure = MagicMock(return_value={'error': 'update error'})
        with patch.multiple(boto_cloudfront,
            __salt__={
                'boto_cloudfront.get_distribution': mock_get,
                'boto_cloudfront.update_distribution': mock_update_failure,
            },
            __opts__={'test': False},
        ):
            comment = 'Error updating distribution {0}: update error'
            self.assertDictEqual(
                boto_cloudfront.present(self.name, self.config, self.tags),
                self.base_ret_with({
                    'result': False,
                    'comment': comment.format(self.name),
                }),
            )

        mock_update_success = MagicMock(return_value={'result': True})
        with patch.multiple(boto_cloudfront,
            __salt__={
                'boto_cloudfront.get_distribution': mock_get,
                'boto_cloudfront.update_distribution': mock_update_success,
            },
            __opts__={'test': False},
        ):
            self.assertDictEqual(
                boto_cloudfront.present(self.name, self.config, self.tags),
                self.base_ret_with({
                    'result': True,
                    'comment': 'Updated distribution {0}.'.format(self.name),
                    'changes': {'diff': diff},
                }),
            )
