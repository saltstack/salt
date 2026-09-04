import io
from textwrap import dedent

import pytest

import salt.modules.solaris_shadow as solaris_shadow
from tests.support.mock import MagicMock, patch

try:
    import pwd

    missing_pwd = False
except ImportError:
    pwd = None
    missing_pwd = True


skip_on_missing_pwd = pytest.mark.skipif(
    missing_pwd, reason="Has no pwd module for accessing /etc/password passwords"
)

# pylint: disable=singleton-comparison

# TODO: A lot of the shadow functionality is common across solaris and Linux.
# It would be possible to combine some of this into salt/utils -W. Werner, 2021-01-26


@pytest.fixture
def configure_loader_modules():
    return {solaris_shadow: {"pwd": pwd}}


@pytest.fixture
def fake_fopen_has_etc_shadow():
    contents = dedent(
        """\
            foo:bar:bang
            whatever:is:shadow
            roscivs:bottia:bloop
        """
    )
    fake_output_shadow_file = io.StringIO()

    def fopen(file, mode="r", *args, **kwargs):
        for line in contents.split():
            if "b" in mode:
                return io.BytesIO(contents.encode())
            elif "w" in mode:
                return fake_output_shadow_file
            else:
                return io.StringIO(contents)

    with patch("salt.utils.files.fopen", side_effect=fopen, autospec=True):
        with patch.object(fake_output_shadow_file, "close"):
            yield fake_output_shadow_file
            fake_output_shadow_file.close()


@pytest.fixture
def fake_getspnam():
    """
    Patch the module-local ``_getspnam`` helper (formerly ``spwd.getspnam``).
    """
    with patch.object(solaris_shadow, "_getspnam", autospec=True) as fake:
        yield fake


@pytest.fixture
def missing_getspnam():
    """
    Simulate ``/etc/shadow`` being unreadable, so the SmartOS-style fallback
    (pwd + ``passwd -s``) is exercised.
    """
    with patch.object(
        solaris_shadow, "_getspnam", autospec=True, side_effect=FileNotFoundError
    ):
        yield


@pytest.fixture
def fake_pwnam():
    with patch(
        "pwd.getpwnam",
        autospec=True,
    ) as fake_pwnam:
        yield fake_pwnam


@pytest.fixture
def has_shadow_file():
    with patch("os.path.isfile", return_value=True):
        yield


@pytest.fixture
def has_not_shadow_file():
    with patch("os.path.isfile", return_value=False):
        yield


def test_when_getspnam_returns_data_results_should_be_returned_from_getspnam(
    fake_getspnam,
):
    expected_results = {
        "name": "roscivs",
        "passwd": "bottia",
        "lstchg": "2010-08-14",
        "min": 0,
        "max": 42,
        "warn": "nope",
        "inact": "whatever",
        "expire": "never!",
    }
    fake_getspnam.return_value.sp_namp = expected_results["name"]
    fake_getspnam.return_value.sp_pwdp = expected_results["passwd"]
    fake_getspnam.return_value.sp_lstchg = expected_results["lstchg"]
    fake_getspnam.return_value.sp_min = expected_results["min"]
    fake_getspnam.return_value.sp_max = expected_results["max"]
    fake_getspnam.return_value.sp_warn = expected_results["warn"]
    fake_getspnam.return_value.sp_inact = expected_results["inact"]
    fake_getspnam.return_value.sp_expire = expected_results["expire"]

    actual_results = solaris_shadow.info(name="roscivs")

    assert actual_results == expected_results


def test_when_getspnam_finds_no_user_and_pwnam_finds_no_user_results_should_be_empty(
    fake_getspnam, fake_pwnam
):
    expected_results = {
        "name": "",
        "passwd": "",
        "lstchg": "",
        "min": "",
        "max": "",
        "warn": "",
        "inact": "",
        "expire": "",
    }
    fake_getspnam.side_effect = KeyError
    fake_pwnam.side_effect = KeyError

    actual_results = solaris_shadow.info(name="roscivs")

    assert actual_results == expected_results


@skip_on_missing_pwd
def test_when_pwd_fallback_is_used_and_no_name_exists_results_should_be_empty(
    missing_getspnam, fake_pwnam
):
    expected_results = {
        "name": "",
        "passwd": "",
        "lstchg": "",
        "min": "",
        "max": "",
        "warn": "",
        "inact": "",
        "expire": "",
    }
    fake_pwnam.side_effect = KeyError

    actual_results = solaris_shadow.info(name="wayne")

    assert actual_results == expected_results


@skip_on_missing_pwd
def test_when_etc_shadow_does_not_exist_info_should_be_empty_except_for_name(
    missing_getspnam, fake_pwnam, has_not_shadow_file
):
    expected_results = {
        "name": "wayne",
        "passwd": "",
        "lstchg": "",
        "min": "",
        "max": "",
        "warn": "",
        "inact": "",
        "expire": "",
    }
    fake_pwnam.return_value.pw_name = "not this name"

    actual_results = solaris_shadow.info(name="wayne")

    assert actual_results == expected_results


@skip_on_missing_pwd
def test_when_etc_shadow_exists_but_name_not_in_shadow_passwd_field_should_be_empty(
    fake_fopen_has_etc_shadow, missing_getspnam, fake_pwnam, has_shadow_file
):
    with patch.dict(
        solaris_shadow.__salt__,
        {"cmd.run_all": MagicMock(return_value={"retcode": 42})},
    ):
        actual_result = solaris_shadow.info(name="badname")

    assert actual_result["passwd"] == ""


@skip_on_missing_pwd
def test_when_name_in_etc_shadow_passwd_should_be_in_info(
    fake_fopen_has_etc_shadow, missing_getspnam, fake_pwnam, has_shadow_file
):
    with patch.dict(
        solaris_shadow.__salt__,
        {"cmd.run_all": MagicMock(return_value={"retcode": 42})},
    ):
        actual_result = solaris_shadow.info(name="roscivs")

    assert actual_result["passwd"] == "bottia"


def test_when_set_password_and_not_has_shadow_ret_should_be_empty_dict(
    has_not_shadow_file,
):
    actual_result = solaris_shadow.set_password(name="fnord", password="blarp")

    assert actual_result == {}


def test_set_password_should_return_False_if_passwd_in_info_is_different_than_new_password(
    has_shadow_file, fake_fopen_has_etc_shadow
):
    existing_password = "Fnord"
    failed_set_password = "ignore me"
    with patch(
        "salt.modules.solaris_shadow.info",
        autospec=True,
        return_value={"passwd": existing_password},
    ):
        actual_result = solaris_shadow.set_password(
            name="roscivs", password=failed_set_password
        )

        assert actual_result == False


def test_when_set_password_and_name_in_shadow_then_password_should_be_changed_for_that_user(
    has_shadow_file, fake_fopen_has_etc_shadow, fake_getspnam
):
    expected_password = "bottia2"
    expected_shadow_contents = dedent(
        """\
            foo:bar:bang
            whatever:is:shadow
            roscivs:bottia2:bloop
        """
    )
    with patch(
        "salt.modules.solaris_shadow.info",
        autospec=True,
        return_value={"passwd": expected_password},
    ):
        actual_result = solaris_shadow.set_password(
            name="roscivs", password=expected_password
        )

    assert fake_fopen_has_etc_shadow.getvalue() == expected_shadow_contents
    assert actual_result == True


@skip_on_missing_pwd
def test_module_import_does_not_reference_spwd():
    """
    Regression test for #64264: ``salt.modules.solaris_shadow`` must not
    import the removed-in-Python-3.13 ``spwd`` module.
    """
    import salt.modules.solaris_shadow as module_under_test

    assert not hasattr(module_under_test, "spwd")
    assert not hasattr(module_under_test, "HAS_SPWD")


def test_getspnam_parses_etc_shadow_and_returns_struct_spwd():
    """
    Regression test for #64264: the replacement ``_getspnam`` reads
    ``/etc/shadow`` directly and returns an ``spwd.struct_spwd``-compatible
    namedtuple.
    """
    shadow_contents = dedent(
        """\
        root:$6$abc$xyz:19000:0:99999:7:::
        roscivs:$6$def$uvw:19100:1:42:14:30:19999:0
        """
    )

    def fopen(file, mode="r", *args, **kwargs):
        return io.StringIO(shadow_contents)

    with patch("salt.utils.files.fopen", side_effect=fopen, autospec=True):
        record = solaris_shadow._getspnam("roscivs")

    assert record.sp_namp == "roscivs"
    assert record.sp_pwdp == "$6$def$uvw"
    assert record.sp_lstchg == 19100
    assert record.sp_min == 1
    assert record.sp_max == 42
    assert record.sp_warn == 14
    assert record.sp_inact == 30
    assert record.sp_expire == 19999
    assert record.sp_flag == 0


def test_getspnam_raises_keyerror_when_user_missing():
    shadow_contents = "root:x:19000:0:99999:7:::\n"

    def fopen(file, mode="r", *args, **kwargs):
        return io.StringIO(shadow_contents)

    with patch("salt.utils.files.fopen", side_effect=fopen, autospec=True):
        with pytest.raises(KeyError):
            solaris_shadow._getspnam("nobody")
