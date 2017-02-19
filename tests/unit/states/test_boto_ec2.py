# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import Salt Libs
from salt.states import boto_ec2


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoEc2TestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.boto_ec2
    '''
    loader_module = boto_ec2

    # 'key_present' function tests: 1

    def test_key_present(self):
        '''
        Test to ensure key pair is present.
        '''
        name = 'mykeypair'
        upublic = 'salt://mybase/public_key.pub'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[True, False, False])
        mock_bool = MagicMock(side_effect=[IOError, True])
        with patch.dict(boto_ec2.__salt__, {'boto_ec2.get_key': mock,
                                            'cp.get_file_str': mock_bool}):
            comt = ('The key name {0} already exists'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(boto_ec2.key_present(name), ret)

            comt = ('File {0} not found.'.format(upublic))
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(boto_ec2.key_present(name,
                                                      upload_public=upublic),
                                 ret)

            with patch.dict(boto_ec2.__opts__, {'test': True}):
                comt = ('The key {0} is set to be created.'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_ec2.key_present
                                     (name, upload_public=upublic), ret)

    # 'key_absent' function tests: 1

    def test_key_absent(self):
        '''
        Test to deletes a key pair
        '''
        name = 'new_table'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(boto_ec2.__salt__, {'boto_ec2.get_key': mock}):
            comt = ('The key name {0} does not exist'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(boto_ec2.key_absent(name), ret)

            with patch.dict(boto_ec2.__opts__, {'test': True}):
                comt = ('The key {0} is set to be deleted.'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(boto_ec2.key_absent(name), ret)
