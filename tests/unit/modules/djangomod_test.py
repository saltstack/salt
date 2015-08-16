# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import djangomod

# Globals
djangomod.__grains__ = {}
djangomod.__salt__ = {}
djangomod.__context__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DjangomodTestCase(TestCase):
    '''
    Test cases for salt.modules.djangomod
    '''
    # 'command' function tests: 1

    @patch('salt.modules.djangomod._get_django_admin',
           MagicMock(return_value=True))
    def test_command(self):
        '''
        Test if it runs arbitrary django management command
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(djangomod.__salt__, {'cmd.run': mock}):
            self.assertTrue(djangomod.command('DJANGO_SETTINGS_MODULE',
                                              'validate'))

    # 'syncdb' function tests: 1

    @patch('salt.modules.djangomod._get_django_admin',
           MagicMock(return_value=True))
    def test_syncdb(self):
        '''
        Test if it runs the Django-Admin syncdb command
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(djangomod.__salt__, {'cmd.run': mock}):
            self.assertTrue(djangomod.syncdb('DJANGO_SETTINGS_MODULE'))

    # 'createsuperuser' function tests: 1

    @patch('salt.modules.djangomod._get_django_admin',
           MagicMock(return_value=True))
    def test_createsuperuser(self):
        '''
        Test if it create a super user for the database.
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(djangomod.__salt__, {'cmd.run': mock}):
            self.assertTrue(djangomod.createsuperuser('DJANGO_SETTINGS_MODULE',
                                                      'SALT',
                                                      'salt@slatstack.com'))

    # 'loaddata' function tests: 1

    @patch('salt.modules.djangomod._get_django_admin',
           MagicMock(return_value=True))
    def test_loaddata(self):
        '''
        Test if it loads fixture data
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(djangomod.__salt__, {'cmd.run': mock}):
            self.assertTrue(djangomod.loaddata('DJANGO_SETTINGS_MODULE',
                                               'mydata'))

    # 'collectstatic' function tests: 1

    @patch('salt.modules.djangomod._get_django_admin',
           MagicMock(return_value=True))
    def test_collectstatic(self):
        '''
        Test if it collect static files from each of your applications
        into a single location
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(djangomod.__salt__, {'cmd.run': mock}):
            self.assertTrue(djangomod.collectstatic('DJANGO_SETTINGS_MODULE'))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DjangomodTestCase, needs_daemon=False)
