# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
from salt.states import artifactory

artifactory.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ArtifactoryTestCase(TestCase):
    '''
    Test cases for salt.states.artifactory
    '''
    # 'downloaded' function tests: 1

    def test_downloaded(self):
        '''
        Test to ensures that the artifact from artifactory exists at
        given location.
        '''
        name = 'jboss'
        arti_url = 'http://artifactory.intranet.example.com/artifactory'
        artifact = {'artifactory_url': arti_url, 'artifact_id': 'module',
                    'repository': 'libs-release-local', 'packaging': 'jar',
                    'group_id': 'com.company.module', 'classifier': 'sources',
                    'version': '1.0'}

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        mck = MagicMock(return_value={'status': False, 'changes': {},
                                      'comment': ''})
        with patch.dict(artifactory.__salt__, {'artifactory.get_release': mck}):
            self.assertDictEqual(artifactory.downloaded(name, artifact), ret)

        with patch.object(artifactory, '__fetch_from_artifactory',
                          MagicMock(side_effect=Exception('error'))):
            ret = artifactory.downloaded(name, artifact)
            self.assertEqual(ret['result'], False)
            self.assertEqual(repr(ret['comment']), repr(Exception('error')))
