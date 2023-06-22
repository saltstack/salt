"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.djangomod
"""
import pytest

import salt.modules.djangomod as djangomod
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    with patch("salt.utils.path.which", lambda exe: exe):
        yield {djangomod: {}}


def test_command():
    """
    Test if it runs arbitrary django management command
    """
    mock = MagicMock(return_value=True)
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        assert djangomod.command("DJANGO_SETTINGS_MODULE", "validate")


def test_syncdb():
    """
    Test if it runs the Django-Admin syncdb command
    """
    mock = MagicMock(return_value=True)
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        assert djangomod.syncdb("DJANGO_SETTINGS_MODULE")


def test_migrate():
    """
    Test if it runs the Django-Admin migrate command
    """
    mock = MagicMock(return_value=True)
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        assert djangomod.migrate("DJANGO_SETTINGS_MODULE")


def test_createsuperuser():
    """
    Test if it create a super user for the database.
    """
    mock = MagicMock(return_value=True)
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        assert djangomod.createsuperuser(
            "DJANGO_SETTINGS_MODULE", "SALT", "salt@slatstack.com"
        )


def test_loaddata():
    """
    Test if it loads fixture data
    """
    mock = MagicMock(return_value=True)
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        assert djangomod.loaddata("DJANGO_SETTINGS_MODULE", "mydata")


def test_collectstatic():
    """
    Test if it collect static files from each of your applications
    into a single location
    """
    mock = MagicMock(return_value=True)
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        assert djangomod.collectstatic("DJANGO_SETTINGS_MODULE")


def test_django_admin_cli_command():
    mock = MagicMock()
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        djangomod.command("settings.py", "runserver")
        mock.assert_called_once_with(
            "django-admin.py runserver --settings=settings.py",
            python_shell=False,
            env=None,
            runas=None,
        )


def test_django_admin_cli_command_with_args():
    mock = MagicMock()
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        djangomod.command(
            "settings.py",
            "runserver",
            None,
            None,
            None,
            None,
            "noinput",
            "somethingelse",
        )
        mock.assert_called_once_with(
            "django-admin.py runserver --settings=settings.py "
            "--noinput --somethingelse",
            python_shell=False,
            env=None,
            runas=None,
        )


def test_django_admin_cli_command_with_kwargs():
    mock = MagicMock()
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        djangomod.command(
            "settings.py", "runserver", None, None, None, database="something"
        )
        mock.assert_called_once_with(
            "django-admin.py runserver --settings=settings.py --database=something",
            python_shell=False,
            env=None,
            runas=None,
        )


def test_django_admin_cli_command_with_kwargs_ignore_dunder():
    mock = MagicMock()
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        djangomod.command(
            "settings.py", "runserver", None, None, None, __ignore="something"
        )
        mock.assert_called_once_with(
            "django-admin.py runserver --settings=settings.py",
            python_shell=False,
            env=None,
            runas=None,
        )


def test_django_admin_cli_syncdb():
    mock = MagicMock()
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        djangomod.syncdb("settings.py")
        mock.assert_called_once_with(
            "django-admin.py syncdb --settings=settings.py --noinput",
            python_shell=False,
            env=None,
            runas=None,
        )


def test_django_admin_cli_syncdb_migrate():
    mock = MagicMock()
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        djangomod.syncdb("settings.py", migrate=True)
        mock.assert_called_once_with(
            "django-admin.py syncdb --settings=settings.py --migrate --noinput",
            python_shell=False,
            env=None,
            runas=None,
        )


def test_django_admin_cli_migrate():
    mock = MagicMock()
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        djangomod.migrate("settings.py")
        mock.assert_called_once_with(
            "django-admin.py migrate --settings=settings.py --noinput",
            python_shell=False,
            env=None,
            runas=None,
        )


def test_django_admin_cli_createsuperuser():
    mock = MagicMock()
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        djangomod.createsuperuser("settings.py", "testuser", "user@example.com")
        assert mock.call_count == 1
        mock.assert_called_with(
            "django-admin.py createsuperuser --settings=settings.py --noinput "
            "--email=user@example.com --username=testuser",
            env=None,
            python_shell=False,
            runas=None,
        )


def no_test_loaddata():
    mock = MagicMock()
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        djangomod.loaddata("settings.py", "app1,app2")
        mock.assert_called_once_with(
            "django-admin.py loaddata --settings=settings.py app1 app2",
        )


def test_django_admin_cli_collectstatic():
    mock = MagicMock()
    with patch.dict(djangomod.__salt__, {"cmd.run": mock}):
        djangomod.collectstatic(
            "settings.py", None, True, "something", True, True, True, True
        )
        mock.assert_called_once_with(
            "django-admin.py collectstatic --settings=settings.py "
            "--noinput --no-post-process --dry-run --clear --link "
            "--no-default-ignore --ignore=something",
            python_shell=False,
            env=None,
            runas=None,
        )
