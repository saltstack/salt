# -*- coding: utf-8 -*-
'''
Test the django module
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import salt libs
from salt.modules import djangomod as django

django.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.utils.which', lambda exe: exe)
class DjangoModuleTest(integration.ModuleCase):
    '''
    Test the django module
    '''

    def test_command(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.command('settings.py', 'runserver')
            mock.assert_called_once_with(
                'django-admin.py runserver --settings=settings.py',
                python_shell=False,
                env=None
            )

    def test_command_with_args(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.command(
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

    def test_command_with_kwargs(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.command(
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

    def test_command_with_kwargs_ignore_dunder(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.command(
                'settings.py', 'runserver', None, None, __ignore='something'
            )
            mock.assert_called_once_with(
                'django-admin.py runserver --settings=settings.py',
                python_shell=False,
                env=None
            )

    def test_syncdb(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.syncdb('settings.py')
            mock.assert_called_once_with(
                'django-admin.py syncdb --settings=settings.py --noinput',
                python_shell=False,
                env=None
            )

    def test_syncdb_migrate(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.syncdb('settings.py', migrate=True)
            mock.assert_called_once_with(
                'django-admin.py syncdb --settings=settings.py --migrate '
                '--noinput',
                python_shell=False,
                env=None
            )

    def test_createsuperuser(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.createsuperuser(
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
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.loaddata('settings.py', 'app1,app2')
            mock.assert_called_once_with(
                'django-admin.py loaddata --settings=settings.py app1 app2',
            )

    def test_collectstatic(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.collectstatic(
                'settings.py', None, True, 'something', True, True, True, True
            )
            mock.assert_called_once_with(
                'django-admin.py collectstatic --settings=settings.py '
                '--noinput --no-post-process --dry-run --clear --link '
                '--no-default-ignore --ignore=something',
                python_shell=False,
                env=None
            )
