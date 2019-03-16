# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.nexus as nexus


@skipIf(NO_MOCK, NO_MOCK_REASON)
class nexusTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.nexus
    '''
    def setup_loader_modules(self):
        return {nexus: {}}

    # 'downloaded' function tests: 1

    def test_downloaded(self):
        '''
        Test to ensures that the artifact from nexus exists at
        given location.
        '''
        name = 'jboss'
        arti_url = 'http://nexus.example.com/repository'
        artifact = {'nexus_url': arti_url, 'artifact_id': 'module',
                    'repository': 'libs-releases', 'packaging': 'jar',
                    'group_id': 'com.company.module', 'classifier': 'sources',
                    'version': '1.0'}

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        mck = MagicMock(return_value={'status': False, 'changes': {},
                                      'comment': ''})
        with patch.dict(nexus.__salt__, {'nexus.get_release': mck}):
            self.assertDictEqual(nexus.downloaded(name, artifact), ret)

        with patch.object(nexus, '__fetch_from_nexus',
                          MagicMock(side_effect=Exception('error'))):
            ret = nexus.downloaded(name, artifact)
            self.assertEqual(ret['result'], False)
            self.assertEqual(ret['comment'], 'error')
