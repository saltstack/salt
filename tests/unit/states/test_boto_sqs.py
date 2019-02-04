# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import textwrap

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import Salt Libs
import salt.config
import salt.loader
import salt.states.boto_sqs as boto_sqs


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoSqsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.boto_sqs
    '''
    def setup_loader_modules(self):
        utils = salt.loader.utils(
            self.opts,
            whitelist=['boto3', 'yaml', 'args', 'systemd', 'path', 'platform'],
            context={})
        return {
            boto_sqs: {
                '__utils__': utils,
            }
        }

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.DEFAULT_MINION_OPTS.copy()

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the SQS queue exists.
        '''
        name = 'mysqs'
        attributes = {'DelaySeconds': 20}
        base_ret = {'name': name, 'changes': {}}

        mock = MagicMock(
            side_effect=[{'result': b} for b in [False, False, True, True]],
        )
        mock_bool = MagicMock(return_value={'error': 'create error'})
        mock_attr = MagicMock(return_value={'result': {}})
        with patch.dict(boto_sqs.__salt__,
                        {'boto_sqs.exists': mock,
                         'boto_sqs.create': mock_bool,
                         'boto_sqs.get_attributes': mock_attr}):
            with patch.dict(boto_sqs.__opts__, {'test': False}):
                comt = ['Failed to create SQS queue {0}: create error'.format(
                    name,
                )]
                ret = base_ret.copy()
                ret.update({'result': False, 'comment': comt})
                self.assertDictEqual(boto_sqs.present(name), ret)

            with patch.dict(boto_sqs.__opts__, {'test': True}):
                comt = ['SQS queue {0} is set to be created.'.format(name)]
                ret = base_ret.copy()
                ret.update({
                    'result': None,
                    'comment': comt,
                    'changes': {'old': None, 'new': 'mysqs'},
                })
                self.assertDictEqual(boto_sqs.present(name), ret)
                diff = textwrap.dedent('''\
                    ---
                    +++
                    @@ -1 +1 @@
                    -{}
                    +DelaySeconds: 20

                ''').splitlines()
                # Difflib adds a trailing space after the +++/--- lines,
                # programatically add them back here. Having them in the test
                # file itself is not feasible since a few popular plugins for
                # vim will remove trailing whitespace.
                for idx in (0, 1):
                    diff[idx] += ' '
                diff = '\n'.join(diff)

                comt = [
                    'SQS queue mysqs present.',
                    'Attribute(s) DelaySeconds set to be updated:\n{0}'.format(
                        diff,
                    ),
                ]
                ret.update({
                    'comment': comt,
                    'changes': {'attributes': {'diff': diff}},
                })
                self.assertDictEqual(boto_sqs.present(name, attributes), ret)

            comt = ['SQS queue mysqs present.']
            ret = base_ret.copy()
            ret.update({'result': True, 'comment': comt})
            self.assertDictEqual(boto_sqs.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the named sqs queue is deleted.
        '''
        name = 'test.example.com.'
        base_ret = {'name': name, 'changes': {}}

        mock = MagicMock(side_effect=[{'result': False}, {'result': True}])
        with patch.dict(boto_sqs.__salt__,
                        {'boto_sqs.exists': mock}):
            comt = ('SQS queue {0} does not exist in None.'.format(name))
            ret = base_ret.copy()
            ret.update({'result': True, 'comment': comt})
            self.assertDictEqual(boto_sqs.absent(name), ret)

            with patch.dict(boto_sqs.__opts__, {'test': True}):
                comt = ('SQS queue {0} is set to be removed.'.format(name))
                ret = base_ret.copy()
                ret.update({
                    'result': None,
                    'comment': comt,
                    'changes': {'old': name, 'new': None},
                })
                self.assertDictEqual(boto_sqs.absent(name), ret)
