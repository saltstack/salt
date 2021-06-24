"""
    :codeauthor: Erik Johnson <erik@saltstack.com>
"""

import textwrap

import pytest
import salt.utils.platform
import salt.utils.stringutils
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import DEFAULT, MagicMock, mock_open, patch
from tests.support.unit import TestCase, skipIf

try:
    import spwd
except ImportError:
    pass

try:
    import salt.modules.linux_shadow as shadow

    HAS_SHADOW = True
except ImportError:
    HAS_SHADOW = False

_PASSWORD = "lamepassword"

# Not testing blowfish as it is not available on most Linux distros
_HASHES = dict(
    md5=dict(pw_salt="TgIp9OTu", pw_hash="$1$TgIp9OTu$.d0FFP6jVi5ANoQmk6GpM1"),
    sha256=dict(
        pw_salt="3vINbSrC",
        pw_hash="$5$3vINbSrC$hH8A04jAY3bG123yU4FQ0wvP678QDTvWBhHHFbz6j0D",
    ),
    sha512=dict(
        pw_salt="PiGA3V2o",
        pw_hash="$6$PiGA3V2o$/PrntRYufz49bRV/V5Eb1V6DdHaS65LB0fu73Tp/xxmDFr6HWJKptY2TvHRDViXZugWpnAcOnrbORpOgZUGTn.",
    ),
)


@skipIf(not salt.utils.platform.is_linux(), "minion is not Linux")
@skipIf(not HAS_SHADOW, "shadow module is not available")
class LinuxShadowTest(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {shadow: {}}

    def test_gen_password(self):
        """
        Test shadow.gen_password
        """
        self.assertTrue(HAS_SHADOW)
        for algorithm, hash_info in _HASHES.items():
            self.assertEqual(
                shadow.gen_password(
                    _PASSWORD, crypt_salt=hash_info["pw_salt"], algorithm=algorithm
                ),
                hash_info["pw_hash"],
            )

    def test_set_password(self):
        """
        Test the corner case in which shadow.set_password is called for a user
        that has an entry in /etc/passwd but not /etc/shadow.
        """
        data = {
            "/etc/shadow": salt.utils.stringutils.to_bytes(
                textwrap.dedent(
                    """\
                foo:orighash:17955::::::
                bar:somehash:17955::::::
                """
                )
            ),
            "*": Exception("Attempted to open something other than /etc/shadow"),
        }
        isfile_mock = MagicMock(
            side_effect=lambda x: True if x == "/etc/shadow" else DEFAULT
        )
        password = "newhash"
        shadow_info_mock = MagicMock(return_value={"passwd": password})

        #
        # CASE 1: Normal password change
        #
        user = "bar"
        user_exists_mock = MagicMock(
            side_effect=lambda x, **y: 0 if x == ["id", user] else DEFAULT
        )
        with patch(
            "salt.utils.files.fopen", mock_open(read_data=data)
        ) as shadow_mock, patch("os.path.isfile", isfile_mock), patch.object(
            shadow, "info", shadow_info_mock
        ), patch.dict(
            shadow.__salt__, {"cmd.retcode": user_exists_mock}
        ), patch.dict(
            shadow.__grains__, {"os": "CentOS"}
        ):
            result = shadow.set_password(user, password, use_usermod=False)

        assert result
        filehandles = shadow_mock.filehandles["/etc/shadow"]
        # We should only have opened twice, once to read the contents and once
        # to write.
        assert len(filehandles) == 2
        # We're rewriting the entire file
        assert filehandles[1].mode == "w+"
        # We should be calling writelines instead of write, to rewrite the
        # entire file.
        assert len(filehandles[1].writelines_calls) == 1
        # Make sure we wrote the correct info
        lines = filehandles[1].writelines_calls[0]
        # Should only have the same two users in the file
        assert len(lines) == 2
        # The first line should be unchanged
        assert lines[0] == "foo:orighash:17955::::::\n"
        # The second line should have the new password hash
        assert lines[1].split(":")[:2] == [user, password]

        #
        # CASE 2: Corner case: no /etc/shadow entry for user
        #
        user = "baz"
        user_exists_mock = MagicMock(
            side_effect=lambda x, **y: 0 if x == ["id", user] else DEFAULT
        )
        with patch(
            "salt.utils.files.fopen", mock_open(read_data=data)
        ) as shadow_mock, patch("os.path.isfile", isfile_mock), patch.object(
            shadow, "info", shadow_info_mock
        ), patch.dict(
            shadow.__salt__, {"cmd.retcode": user_exists_mock}
        ), patch.dict(
            shadow.__grains__, {"os": "CentOS"}
        ):
            result = shadow.set_password(user, password, use_usermod=False)

        assert result
        filehandles = shadow_mock.filehandles["/etc/shadow"]
        # We should only have opened twice, once to read the contents and once
        # to write.
        assert len(filehandles) == 2
        # We're just appending to the file, not rewriting
        assert filehandles[1].mode == "a+"
        # We should only have written to the file once
        assert len(filehandles[1].write_calls) == 1
        # Make sure we wrote the correct info
        assert filehandles[1].write_calls[0].split(":")[:2] == [user, password]

    def test_info(self):
        """
        Test if info shows the correct user information
        """

        # First test is with a succesful call
        expected_result = [
            ("expire", -1),
            ("inact", -1),
            ("lstchg", 31337),
            ("max", 99999),
            ("min", 0),
            ("name", "foo"),
            ("passwd", _HASHES["sha512"]["pw_hash"]),
            ("warn", 7),
        ]
        getspnam_return = spwd.struct_spwd(
            ["foo", _HASHES["sha512"]["pw_hash"], 31337, 0, 99999, 7, -1, -1, -1]
        )
        with patch("spwd.getspnam", return_value=getspnam_return):
            result = shadow.info("foo")
            self.assertEqual(
                expected_result, sorted(result.items(), key=lambda x: x[0])
            )

        # The next two is for a non-existent user
        expected_result = [
            ("expire", ""),
            ("inact", ""),
            ("lstchg", ""),
            ("max", ""),
            ("min", ""),
            ("name", ""),
            ("passwd", ""),
            ("warn", ""),
        ]
        # We get KeyError exception for non-existent users in glibc based systems
        getspnam_return = KeyError
        with patch("spwd.getspnam", side_effect=getspnam_return):
            result = shadow.info("foo")
            self.assertEqual(
                expected_result, sorted(result.items(), key=lambda x: x[0])
            )
        # And FileNotFoundError in musl based systems
        getspnam_return = FileNotFoundError
        with patch("spwd.getspnam", side_effect=getspnam_return):
            result = shadow.info("foo")
            self.assertEqual(
                expected_result, sorted(result.items(), key=lambda x: x[0])
            )

    @pytest.mark.skip_if_not_root
    def test_list_users(self):
        """
        Test if it returns a list of all users
        """
        self.assertTrue(shadow.list_users())
