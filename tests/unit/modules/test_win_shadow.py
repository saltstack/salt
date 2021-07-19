"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import salt.modules.win_shadow as win_shadow
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class WinShadowTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.win_shadow
    """

    def setup_loader_modules(self):
        return {
            win_shadow: {
                "__salt__": {
                    #                    'user.info': MagicMock(return_value=True),
                    "user.update": MagicMock(return_value=True)
                }
            }
        }

    # 'info' function tests: 1

    def test_info(self):
        """
        Test if it return information for the specified user
        """
        mock_user_info = MagicMock(
            return_value={"name": "SALT", "password_changed": "", "expiration_date": ""}
        )
        with patch.dict(win_shadow.__salt__, {"user.info": mock_user_info}):
            self.assertDictEqual(
                win_shadow.info("SALT"),
                {
                    "name": "SALT",
                    "passwd": "Unavailable",
                    "lstchg": "",
                    "min": "",
                    "max": "",
                    "warn": "",
                    "inact": "",
                    "expire": "",
                },
            )

    # 'set_password' function tests: 1

    def test_set_password(self):
        """
        Test if it set the password for a named user.
        """
        mock_cmd = MagicMock(return_value={"retcode": False})
        mock_user_info = MagicMock(
            return_value={"name": "SALT", "password_changed": "", "expiration_date": ""}
        )
        with patch.dict(
            win_shadow.__salt__, {"cmd.run_all": mock_cmd, "user.info": mock_user_info}
        ):
            self.assertTrue(win_shadow.set_password("root", "mysecretpassword"))
