"""
    :codeauthor: Erik Johnson <erik@saltstack.com>
"""

import types

import pytest

from tests.support.mock import DEFAULT, MagicMock, mock_open, patch

pytestmark = [
    pytest.mark.skip_unless_on_linux,
]

shadow = pytest.importorskip(
    "salt.modules.linux_shadow", reason="shadow module is not available"
)
spwd = pytest.importorskip(
    "spwd", reason="Standard library spwd module is not available"
)


def _pw_hash_ids(value):
    return value.algorithm


@pytest.fixture(
    params=[
        types.SimpleNamespace(
            algorithm="md5",
            clear="lamepassword",
            pw_salt="TgIp9OTu",
            pw_hash="$1$TgIp9OTu$.d0FFP6jVi5ANoQmk6GpM1",
            pw_hash_passlib="$1$TgIp9OTu$.d0FFP6jVi5ANoQmk6GpM1",
        ),
        types.SimpleNamespace(
            algorithm="sha256",
            clear="lamepassword",
            pw_salt="3vINbSrC",
            pw_hash="$5$3vINbSrC$hH8A04jAY3bG123yU4FQ0wvP678QDTvWBhHHFbz6j0D",
            pw_hash_passlib="$5$rounds=535000$3vINbSrC$YUDOmjJNDLWhL2Z7aAdLJnGIAsbUgkHNEcdUUujHHy8",
        ),
        types.SimpleNamespace(
            algorithm="sha512",
            clear="lamepassword",
            pw_salt="PiGA3V2o",
            pw_hash="$6$PiGA3V2o$/PrntRYufz49bRV/V5Eb1V6DdHaS65LB0fu73Tp/xxmDFr6HWJKptY2TvHRDViXZugWpnAcOnrbORpOgZUGTn.",
            pw_hash_passlib="$6$rounds=656000$PiGA3V2o$eaAfTU0e1iUFcQycB94otS66/hTgVj94VIAaDp9IJHagSQ.gZascQYOE5.RO87kSY52lJ1LoYX8LNVa2OG8/U/",
        ),
    ],
    ids=_pw_hash_ids,
)
def password(request):
    # Not testing blowfish as it is not available on most Linux distros
    return request.param


@pytest.fixture(params=["crypto", "passlib"])
def library(request):
    with patch("salt.utils.pycrypto.HAS_CRYPT", request.param == "crypto"):
        yield request.param


@pytest.fixture
def configure_loader_modules():
    return {shadow: {}}


def test_gen_password(password, library):
    """
    Test shadow.gen_password
    """
    if library == "passlib":
        pw_hash = password.pw_hash_passlib
    else:
        pw_hash = password.pw_hash
    assert (
        shadow.gen_password(
            password.clear,
            crypt_salt=password.pw_salt,
            algorithm=password.algorithm,
        )
        == pw_hash
    )


def test_set_password():
    """
    Test the corner case in which shadow.set_password is called for a user
    that has an entry in /etc/passwd but not /etc/shadow.
    """
    original_lines = [
        "foo:orighash:17955::::::\n",
        "bar:somehash:17955::::::\n",
    ]

    data = {
        "/etc/shadow": "".join(original_lines),
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
        assert shadow.set_password(user, password, use_usermod=False)

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
    assert lines[0] == original_lines[0]
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
        assert shadow.set_password(user, password, use_usermod=False)

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


def test_info(password):
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
        ("passwd", password.pw_hash),
        ("warn", 7),
    ]
    getspnam_return = spwd.struct_spwd(
        ["foo", password.pw_hash, 31337, 0, 99999, 7, -1, -1, -1]
    )
    with patch("spwd.getspnam", return_value=getspnam_return):
        result = shadow.info("foo")
        assert expected_result == sorted(result.items(), key=lambda x: x[0])

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
        assert expected_result == sorted(result.items(), key=lambda x: x[0])
    # And FileNotFoundError in musl based systems
    getspnam_return = FileNotFoundError
    with patch("spwd.getspnam", side_effect=getspnam_return):
        result = shadow.info("foo")
        assert expected_result == sorted(result.items(), key=lambda x: x[0])


def test_set_password_malformed_shadow_entry():
    """
    Test that Salt will repair a malformed shadow entry (that is, one that
    doesn't have the correct number of fields).
    """
    original_lines = [
        "valid:s00persekr1thash:17955::::::\n",
        "tooshort:orighash:17955:::::\n",
        "toolong:orighash:17955:::::::\n",
    ]
    data = {
        "/etc/shadow": "".join(original_lines),
        "*": Exception("Attempted to open something other than /etc/shadow"),
    }
    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == "/etc/shadow" else DEFAULT
    )
    password = "newhash"
    shadow_info_mock = MagicMock(return_value={"passwd": password})

    #
    # CASE 1: Fix an entry with too few fields
    #
    user = "tooshort"
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
        assert shadow.set_password(user, password, use_usermod=False)

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
    # Should only have the same three users in the file
    assert len(lines) == 3
    # The first and third line should be unchanged
    assert lines[0] == original_lines[0]
    assert lines[2] == original_lines[2]
    # The second line should have the new password hash, and it should have
    # gotten "fixed" by adding another colon.
    fixed = lines[1].split(":")
    assert fixed[:2] == [user, password]
    assert len(fixed) == 9

    #
    # CASE 2: Fix an entry with too many fields
    #
    user = "toolong"
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
        assert shadow.set_password(user, password, use_usermod=False)

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
    # Should only have the same three users in the file
    assert len(lines) == 3
    # The first and second line should be unchanged
    assert lines[0] == original_lines[0]
    assert lines[1] == original_lines[1]
    # The third line should have the new password hash, and it should have
    # gotten "fixed" by reducing it to 9 fields instead of 10.
    fixed = lines[2].split(":")
    assert fixed[:2] == [user, password]
    assert len(fixed) == 9


@pytest.mark.skip_if_not_root
def test_list_users():
    """
    Test if it returns a list of all users
    """
    assert shadow.list_users()
