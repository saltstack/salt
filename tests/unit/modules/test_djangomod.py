# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.djangomod as djangomod


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.utils.which', lambda exe: exe)
class DjangomodTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.djangomod
    '''
    def setup_loader_modules(self):
        return {djangomod: {}}

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

    def test_django_admin_cli_command(self):
        mock = MagicMock()
        with patch.dict(djangomod.__salt__,
                        {'cmd.run': mock}):
            djangomod.command('settings.py', 'runserver')
            mock.assert_called_once_with(
                'django-admin.py runserver --settings=settings.py',
                python_shell=False,
                env=None
            )

    def test_django_admin_cli_command_with_args(self):
        mock = MagicMock()
        with patch.dict(djangomod.__salt__,
                        {'cmd.run': mock}):
            djangomod.command(
                'settings.py',
                'runserver',
                None,
                None,
                None,
                'noinput',
                'somethingelse'
            )
            mock.assert_called_once_with(
                'django-admin.py runserver --settings=settings.py '
                '--noinput --somethingelse',
                python_shell=False,
                env=None
            )

    def test_django_admin_cli_command_with_kwargs(self):
        mock = MagicMock()
        with patch.dict(djangomod.__salt__,
                        {'cmd.run': mock}):
            djangomod.command(
                'settings.py',
                'runserver',
                None,
                None,
                database='something'
            )
            mock.assert_called_once_with(
                'django-admin.py runserver --settings=settings.py '
                '--database=something',
                python_shell=False,
                env=None
            )

    def test_django_admin_cli_command_with_kwargs_ignore_dunder(self):
        mock = MagicMock()
        with patch.dict(djangomod.__salt__,
                        {'cmd.run': mock}):
            djangomod.command(
                'settings.py', 'runserver', None, None, __ignore='something'
            )
            mock.assert_called_once_with(
                'django-admin.py runserver --settings=settings.py',
                python_shell=False,
                env=None
            )

    def test_django_admin_cli_syncdb(self):
        mock = MagicMock()
        with patch.dict(djangomod.__salt__,
                        {'cmd.run': mock}):
            djangomod.syncdb('settings.py')
            mock.assert_called_once_with(
                'django-admin.py syncdb --settings=settings.py --noinput',
                python_shell=False,
                env=None
            )

    def test_django_admin_cli_syncdb_migrate(self):
        mock = MagicMock()
        with patch.dict(djangomod.__salt__,
                        {'cmd.run': mock}):
            djangomod.syncdb('settings.py', migrate=True)
            mock.assert_called_once_with(
                'django-admin.py syncdb --settings=settings.py --migrate '
                '--noinput',
                python_shell=False,
                env=None
            )

    def test_django_admin_cli_createsuperuser(self):
        mock = MagicMock()
        with patch.dict(djangomod.__salt__,
                        {'cmd.run': mock}):
            djangomod.createsuperuser(
                'settings.py', 'testuser', 'user@example.com'
            )
            mock.assert_called_once_with(
                'django-admin.py createsuperuser --settings=settings.py '
                '--noinput --username=testuser --email=user@example.com',
                python_shell=False,
                env=None
            )

    def no_test_loaddata(self):
        mock = MagicMock()
        with patch.dict(djangomod.__salt__,
                        {'cmd.run': mock}):
            djangomod.loaddata('settings.py', 'app1,app2')
            mock.assert_called_once_with(
                'django-admin.py loaddata --settings=settings.py app1 app2',
            )

    def test_django_admin_cli_collectstatic(self):
        mock = MagicMock()
        with patch.dict(djangomod.__salt__,
                        {'cmd.run': mock}):
            djangomod.collectstatic(
                'settings.py', None, True, 'something', True, True, True, True
            )
            mock.assert_called_once_with(
                'django-admin.py collectstatic --settings=settings.py '
                '--noinput --no-post-process --dry-run --clear --link '
                '--no-default-ignore --ignore=something',
                python_shell=False,
                env=None
            )
