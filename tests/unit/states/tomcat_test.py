# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import tomcat

# Globals
tomcat.__salt__ = {}
tomcat.__opts__ = {}
tomcat.__env__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TomcatTestCase(TestCase):
    '''
        Validate the tomcat state
    '''
    def test_war_deployed(self):
        '''
            Test to enforce that the WAR will be deployed and
            started in the context path it will make use of WAR versions
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock1 = MagicMock(return_value='saltstack')
        mock2 = MagicMock(side_effect=['FAIL', 'saltstack'])
        mock3 = MagicMock(return_value='deploy')
        mock = MagicMock(side_effect=[{'salt': {'version': 'jenkins-1.20.4',
                                                'mode': 'running'}},
                                      {'salt': {'version': '1'}},
                                      {'salt': {'version': 'jenkins-1.2.4',
                                                'mode': 'run'}},
                                      {'salt': {'version': '1'}},
                                      {'salt': {'version': '1'}}])
        with patch.dict(tomcat.__salt__, {"tomcat.ls": mock,
                                          'tomcat.start': mock1,
                                          'tomcat.undeploy': mock2,
                                          'tomcat.deploy_war': mock3}):
            ret.update({'comment': 'salt in version 1.20.4'
                        ' is already deployed'})
            self.assertDictEqual(tomcat.war_deployed('salt',
                                                     'salt://jenkins'
                                                     '-1.20.4.war'), ret)

            with patch.dict(tomcat.__opts__, {"test": True}):
                ret.update({'changes': {'deploy': 'will deploy salt'
                                        ' in version 1.2.4',
                                        'undeploy': 'undeployed salt'
                                        ' in version 1'},
                            'result': None, 'comment': ''})
                self.assertDictEqual(tomcat.war_deployed('salt',
                                                         'salt://jenkins'
                                                         '-1.2.4.war'), ret)

            with patch.dict(tomcat.__opts__, {"test": False}):
                ret.update({'changes': {'start': 'starting salt'},
                            'comment': 'saltstack', 'result': False})
                self.assertDictEqual(tomcat.war_deployed('salt',
                                                         'salt://jenkins'
                                                         '-1.2.4.war'), ret)

                ret.update({'changes': {'deploy': 'will deploy salt in'
                                        ' version 1.2.4',
                                        'undeploy': 'undeployed salt in'
                                        ' version 1'},
                            'comment': 'FAIL'})
                self.assertDictEqual(tomcat.war_deployed('salt',
                                                         'salt://jenkins'
                                                         '-1.2.4.war'), ret)

                ret.update({'changes': {'undeploy': 'undeployed salt'
                                        ' in version 1'},
                            'comment': 'deploy'})
                self.assertDictEqual(tomcat.war_deployed('salt',
                                                         'salt://jenkins'
                                                         '-1.2.4.war'), ret)

    def test_wait(self):
        '''
            Test to wait for the tomcat manager to load
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': 'tomcat manager is ready'}
        mock = MagicMock(return_value=True)
        with patch.dict(tomcat.__salt__, {"tomcat.status": mock}):
            self.assertDictEqual(tomcat.wait('salt'), ret)

    def test_mod_watch(self):
        '''
            Test to the tomcat watcher function.
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': 'True'}
        mock = MagicMock(return_value='True')
        with patch.dict(tomcat.__salt__, {"tomcat.reload": mock}):
            ret.update({'changes': {'salt': False}})
            self.assertDictEqual(tomcat.mod_watch('salt'), ret)

    def test_undeployed(self):
        '''
            Test to enforce that the WAR will be un-deployed from the server
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': 'True'}
        mock = MagicMock(side_effect=[False, True, True, True, True])
        mock1 = MagicMock(side_effect=[{'salt': {'a': 1}},
                                       {'salt': {'version': 1}},
                                       {'salt': {'version': 1}},
                                       {'salt': {'version': 1}}])
        mock2 = MagicMock(side_effect=['FAIL', 'saltstack'])
        with patch.dict(tomcat.__salt__, {"tomcat.status": mock,
                                          "tomcat.ls": mock1,
                                          "tomcat.undeploy": mock2}):
            ret.update({'comment': 'Tomcat Manager does not response'})
            self.assertDictEqual(tomcat.undeployed('salt'), ret)

            ret.update({'comment': '', 'result': True})
            self.assertDictEqual(tomcat.undeployed('salt'), ret)

            with patch.dict(tomcat.__opts__, {"test": True}):
                ret.update({'changes': {'undeploy': 1}, 'result': None})
                self.assertDictEqual(tomcat.undeployed('salt'), ret)

            with patch.dict(tomcat.__opts__, {"test": False}):
                ret.update({'changes': {'undeploy': 1},
                            'comment': 'FAIL', 'result': False})
                self.assertDictEqual(tomcat.undeployed('salt'), ret)

                ret.update({'changes': {'undeploy': 1},
                            'comment': '', 'result': True})
                self.assertDictEqual(tomcat.undeployed('salt'), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TomcatTestCase, needs_daemon=False)
