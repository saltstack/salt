"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.composer as composer
from salt.exceptions import SaltException
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {composer: {}}


def test_installed():
    """
    Test to verify that the correct versions of composer
    dependencies are present.
    """
    name = "CURL"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock = MagicMock(return_value=True)
    with patch.dict(composer.__salt__, {"composer.did_composer_install": mock}):
        comt = "Composer already installed this directory"
        ret.update({"comment": comt})
        assert composer.installed(name, always_check=False) == ret

        with patch.dict(composer.__opts__, {"test": True}):
            comt = 'The state of "CURL" will be changed.'
            changes = {
                "new": "composer install will be run in CURL",
                "old": "composer install has been run in CURL",
            }
            ret.update({"comment": comt, "result": None, "changes": changes})
            assert composer.installed(name) == ret

        with patch.dict(composer.__opts__, {"test": False}):
            mock = MagicMock(side_effect=[SaltException, {}])
            with patch.dict(composer.__salt__, {"composer.install": mock}):
                comt = "Error executing composer in 'CURL': "
                ret.update({"comment": comt, "result": False, "changes": {}})
                assert composer.installed(name) == ret

                comt = (
                    "Composer install completed successfully, output silenced by quiet"
                    " flag"
                )
                ret.update({"comment": comt, "result": True})
                assert composer.installed(name, quiet=True) == ret


def test_update():
    """
    Test to composer update the directory to ensure we have
    the latest versions of all project dependencies.
    """
    name = "CURL"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    changes = {
        "new": "composer install/update will be run in CURL",
        "old": "composer install has not yet been run in CURL",
    }

    mock = MagicMock(return_value=True)
    with patch.dict(composer.__salt__, {"composer.did_composer_install": mock}):
        with patch.dict(composer.__opts__, {"test": True}):
            comt = 'The state of "CURL" will be changed.'
            ret.update({"comment": comt, "result": None, "changes": changes})
            assert composer.update(name) == ret

        with patch.dict(composer.__opts__, {"test": False}):
            mock = MagicMock(side_effect=[SaltException, {}])
            with patch.dict(composer.__salt__, {"composer.update": mock}):
                comt = "Error executing composer in 'CURL': "
                ret.update({"comment": comt, "result": False, "changes": {}})
                assert composer.update(name) == ret

                comt = (
                    "Composer update completed successfully, output silenced by quiet"
                    " flag"
                )
                ret.update({"comment": comt, "result": True})
                assert composer.update(name, quiet=True) == ret
