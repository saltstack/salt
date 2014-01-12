# -*- coding: utf-8 -*-

'''
Test the django module
'''
# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

# Import salt libs
import integration
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
                env=None
            )

    def test_syncdb(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.syncdb('settings.py')
            mock.assert_called_once_with(
                'django-admin.py syncdb --settings=settings.py --noinput',
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
                '--no-default-ignore --ignore=something', env=None
            )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DjangoModuleTest)
