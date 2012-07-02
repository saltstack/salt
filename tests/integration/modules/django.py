'''
Test the django module
'''
# Import python libs
import sys

# Import Salt libs
from saltunittest import TestLoader, TextTestRunner, skipIf
import integration
from integration import TestDaemon
from salt.modules import django
django.__salt__ = {}

try:
    from mock import MagicMock, patch
    has_mock = True
except ImportError:
    has_mock = False


@skipIf(has_mock is False, "mock python module is unavailable")
class DjangoModuleTest(integration.ModuleCase):
    '''
    Test the django module
    '''

    def test_command(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.command('settings.py', 'runserver')
            mock.assert_called_once_with('django-admin.py runserver --settings=settings.py')

    def test_command_with_args(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.command('settings.py', 'runserver', None, None, 'noinput', 'somethingelse')
            mock.assert_called_once_with('django-admin.py runserver --settings=settings.py --noinput --somethingelse')

    def test_command_with_kwargs(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.command('settings.py', 'runserver', None, None, database='something')
            mock.assert_called_once_with('django-admin.py runserver --settings=settings.py --database=something')

    def test_command_with_kwargs_ignore_dunder(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.command('settings.py', 'runserver', None, None, __ignore='something')
            mock.assert_called_once_with('django-admin.py runserver --settings=settings.py')

    def test_syncdb(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.syncdb('settings.py')
            mock.assert_called_once_with('django-admin.py syncdb --settings=settings.py --noinput')

    def test_syncdb_migrate(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.syncdb('settings.py', migrate=True)
            mock.assert_called_once_with('django-admin.py syncdb --settings=settings.py --migrate --noinput')

    def test_createsuperuser(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.createsuperuser('settings.py', 'testuser', 'user@example.com')
            mock.assert_called_once_with('django-admin.py createsuperuser --settings=settings.py --noinput --username=testuser --email=user@example.com')

    def test_loaddata(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.loaddata('settings.py', 'app1,app2')
            mock.assert_called_once_with('django-admin.py loaddata --settings=settings.py app1 app2')

    def test_collectstatic(self):
        mock = MagicMock()
        with patch.dict(django.__salt__,
                        {'cmd.run': mock}):
            django.collectstatic('settings.py', None, True, 'something', True, True, True, True)
            mock.assert_called_once_with('django-admin.py collectstatic --settings=settings.py --no-post-process --dry-run --clear --link --no-default-ignore --ignore=something')


if __name__ == '__main__':
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(DjangoModuleTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
