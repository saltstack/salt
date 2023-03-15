import datetime
import sys
import warnings

import pytest
from packaging.version import InvalidVersion

import salt.modules.cmdmod
import salt.utils.versions
import salt.version
from salt.utils.versions import LooseVersion, Version
from tests.support.mock import patch


def test_prerelease():
    version = Version("1.2.3a1")
    assert version.release == (1, 2, 3)
    assert version.pre == ("a", 1)
    assert str(version) == "1.2.3a1"

    version = Version("1.2.0")
    assert str(version) == "1.2.0"


@pytest.mark.parametrize(
    "v1,v2,wanted",
    (
        ("1.5.1", "1.5.2b2", -1),
        ("161", "3.10a", 1),
        ("8.02", "8.02", 0),
        ("3.4j", "1996.07.12", InvalidVersion),
        ("3.2.pl0", "3.1.1.6", InvalidVersion),
        ("2g6", "11g", InvalidVersion),
        ("0.9", "2.2", -1),
        ("1.2.1", "1.2", 1),
        ("1.1", "1.2.2", -1),
        ("1.2", "1.1", 1),
        ("1.2.1", "1.2.2", -1),
        ("1.2.2", "1.2", 1),
        ("1.2", "1.2.2", -1),
        ("0.4.0", "0.4", 0),
        ("1.13++", "5.5.kw", InvalidVersion),
        ("1.1.1a1", "1.1.1", -1),
    ),
)
def test_cmp_strict(v1, v2, wanted):
    try:
        v1i = Version(v1)
        v2i = Version(v2)
        if v1i == v2i:
            res = 0
        elif v1i < v2i:
            res = -1
        elif v1i > v2i:
            res = 1
        assert res == wanted, "cmp({}, {}) should be {}, got {}".format(
            v1, v2, wanted, res
        )
    except InvalidVersion:
        if wanted is not InvalidVersion:
            raise AssertionError(
                "cmp({}, {}) shouldn't raise InvalidVersion".format(v1, v2)
            )


@pytest.mark.parametrize(
    "v1,v2,wanted",
    (
        ("1.5.1", "1.5.2b2", -1),
        ("161", "3.10a", 1),
        ("8.02", "8.02", 0),
        ("3.4j", "1996.07.12", -1),
        ("3.2.pl0", "3.1.1.6", 1),
        ("2g6", "11g", -1),
        ("0.960923", "2.2beta29", -1),
        ("1.13++", "5.5.kw", -1),
        # Added by us
        ("3.10.0-514.el7", "3.10.0-514.6.1.el7", 1),
        ("2.2.2", "2.12.1", -1),
    ),
)
def test_cmp(v1, v2, wanted):
    res = LooseVersion(v1)._cmp(LooseVersion(v2))
    assert res == wanted, "cmp({}, {}) should be {}, got {}".format(v1, v2, wanted, res)


def test_compare():
    ret = salt.utils.versions.compare("1.0", "==", "1.0")
    assert ret

    ret = salt.utils.versions.compare("1.0", "!=", "1.0")
    assert not ret

    with patch.object(salt.utils.versions, "log") as log_mock:
        ret = salt.utils.versions.compare(
            "1.0", "HAH I AM NOT A COMP OPERATOR! I AM YOUR FATHER!", "1.0"
        )
        assert log_mock.error.called


@pytest.mark.parametrize(
    "version",
    (
        "Chlorine",
        3007,
        (3007, 0),
        salt.version.SaltVersionsInfo.CHLORINE,
    ),
)
def test_warn_until_good_version_argument(version):
    with pytest.raises(
        RuntimeError,
        match=(
            r"The warning triggered on filename \'(.*)test_versions.py\', "
            r"line number ([\d]+), is supposed to be shown until version "
            r"3007.0 \(Chlorine\) is released. Current version is now 3009.0 \(Potassium\). "
            r"Please remove the warning."
        ),
    ):
        salt.utils.versions.warn_until(
            version, "Deprecation Message after {version}!", _version_info_=(3009, 0)
        )


def test_warn_until_bad_version_name_raises_runtime_error():
    # Ensure proper behavior
    with warnings.catch_warnings(record=True) as recorded_warnings:
        salt.utils.versions.warn_until(
            "Sodium", "Deprecation Message!", _version_info_=(3000, 0)
        )
        assert "Deprecation Message!" == str(recorded_warnings[0].message)

    with pytest.raises(
        RuntimeError, match="Incorrect spelling for the release name in .*"
    ):
        salt.utils.versions.warn_until(
            "Sudium", "Deprecation Message!", _version_info_=(3000, 0)
        )


def test_kwargs_warn_until():
    # Test invalid version arg
    pytest.raises(RuntimeError, salt.utils.versions.kwargs_warn_until, {}, [])


def test_warn_until_warning_raised(subtests):
    # We *always* want *all* warnings thrown on this module
    warnings.filterwarnings("always", "", DeprecationWarning, __name__)

    def raise_warning(_version_info_=(0, 16, 0)):
        salt.utils.versions.warn_until(
            (0, 17), "Deprecation Message!", _version_info_=_version_info_
        )

    def raise_named_version_warning(_version_info_=(0, 16, 0)):
        salt.utils.versions.warn_until(
            "hydrogen", "Deprecation Message!", _version_info_=_version_info_
        )

    with subtests.test(
        "raise_warning should show warning until version info is >= (0, 17)"
    ):
        with warnings.catch_warnings(record=True) as recorded_warnings:
            raise_warning()
            assert "Deprecation Message!" == str(recorded_warnings[0].message)

    with subtests.test(
        "raise_warning should show warning until version info is >= (0, 17)"
    ):
        with warnings.catch_warnings(record=True) as recorded_warnings:
            raise_named_version_warning()
            assert "Deprecation Message!" == str(recorded_warnings[0].message)

    with subtests.test(
        "the deprecation warning is not issued because we passed _dont_call_warning"
    ):
        with warnings.catch_warnings(record=True) as recorded_warnings:
            salt.utils.versions.warn_until(
                (0, 17), "Foo", _dont_call_warnings=True, _version_info_=(0, 16)
            )
            assert 0 == len(recorded_warnings)

    with subtests.test(
        "Let's set version info to (0, 17), a RuntimeError should be raised"
    ):
        with pytest.raises(
            RuntimeError,
            match=(
                r"The warning triggered on filename \'(.*)test_versions.py\', "
                r"line number ([\d]+), is supposed to be shown until version "
                r"0.17.0 is released. Current version is now 0.17.0. "
                r"Please remove the warning."
            ),
        ):
            raise_warning(_version_info_=(0, 17, 0))

    with subtests.test(
        "Let's set version info to (sys,maxsize, 16, 0), a RuntimeError should be raised"
    ):
        with pytest.raises(
            RuntimeError,
            match=(
                r"The warning triggered on filename \'(.*)test_versions.py\', "
                r"line number ([\d]+), is supposed to be shown until version "
                r"(.*) is released. Current version is now "
                r"([\d.]+). Please remove the warning."
            ),
        ):
            raise_named_version_warning(_version_info_=(sys.maxsize, 16, 0))

    with subtests.test(
        "Even though we're calling warn_until, we pass _dont_call_warnings "
        "because we're only after the RuntimeError"
    ):
        with pytest.raises(
            RuntimeError,
            match=(
                r"The warning triggered on filename \'(.*)test_versions.py\', "
                r"line number ([\d]+), is supposed to be shown until version "
                r"0.17.0 is released. Current version is now "
                r"(.*). Please remove the warning."
            ),
        ):
            salt.utils.versions.warn_until((0, 17), "Foo", _dont_call_warnings=True)

        with pytest.raises(
            RuntimeError,
            match=(
                r"The warning triggered on filename \'(.*)test_versions.py\', "
                r"line number ([\d]+), is supposed to be shown until version "
                r"(.*) is released. Current version is now "
                r"(.*). Please remove the warning."
            ),
        ):
            salt.utils.versions.warn_until(
                "Hydrogen",
                "Foo",
                _dont_call_warnings=True,
                _version_info_=(sys.maxsize, 16, 0),
            )

    with subtests.test("version on the deprecation message gets properly formatted"):
        with warnings.catch_warnings(record=True) as recorded_warnings:
            vrs = salt.version.SaltStackVersion.from_name("Helium")
            salt.utils.versions.warn_until(
                "Helium",
                "Deprecation Message until {version}!",
                _version_info_=(vrs.major - 1, 0),
            )
            assert "Deprecation Message until {}!".format(vrs.formatted_version) == str(
                recorded_warnings[0].message
            )


def test_kwargs_warn_until_warning_raised(subtests):
    # We *always* want *all* warnings thrown on this module
    warnings.filterwarnings("always", "", DeprecationWarning, __name__)

    def raise_warning(**kwargs):
        _version_info_ = kwargs.pop("_version_info_", (0, 16, 0))
        salt.utils.versions.kwargs_warn_until(
            kwargs, (0, 17), _version_info_=_version_info_
        )

    with subtests.test(
        "raise_warning({...}) should show warning until version info is >= (0, 17)"
    ):
        with warnings.catch_warnings(record=True) as recorded_warnings:
            raise_warning(foo=42)  # with a kwarg
            expected = (
                "The following parameter(s) have been deprecated and will be "
                "removed in '0.17.0': 'foo'."
            )
            assert expected == str(recorded_warnings[0].message)

    with subtests.test(
        "With no **kwargs, should not show warning until version info is >= (0, 17)"
    ):
        with warnings.catch_warnings(record=True) as recorded_warnings:
            salt.utils.versions.kwargs_warn_until(
                {}, (0, 17), _version_info_=(0, 16, 0)  # no kwargs
            )
            assert 0 == len(recorded_warnings)

    with subtests.test(
        "Let's set version info to (0, 17), a RuntimeError should be raised "
        "regardless of whether or not we pass any **kwargs."
    ):
        with pytest.raises(
            RuntimeError,
            match=(
                r"The warning triggered on filename \'(.*)test_versions.py\', "
                r"line number ([\d]+), is supposed to be shown until version "
                r"0.17.0 is released. Current version is now 0.17.0. "
                r"Please remove the warning."
            ),
        ):
            raise_warning(_version_info_=(0, 17))  # no kwargs

        with pytest.raises(
            RuntimeError,
            match=(
                r"The warning triggered on filename \'(.*)test_versions.py\', "
                r"line number ([\d]+), is supposed to be shown until version "
                r"0.17.0 is released. Current version is now 0.17.0. "
                r"Please remove the warning."
            ),
        ):
            raise_warning(bar="baz", qux="quux", _version_info_=(0, 17))  # some kwargs


def test_warn_until_date_warning_raised():
    # We *always* want *all* warnings thrown on this module
    warnings.filterwarnings("always", "", DeprecationWarning, __name__)

    _current_date = datetime.date(2000, 1, 1)

    # Test warning with datetime.date instance
    with warnings.catch_warnings(record=True) as recorded_warnings:
        salt.utils.versions.warn_until_date(
            datetime.date(2000, 1, 2),
            "Deprecation Message!",
            _current_date=_current_date,
        )
        assert "Deprecation Message!" == str(recorded_warnings[0].message)

    # Test warning with datetime.datetime instance
    with warnings.catch_warnings(record=True) as recorded_warnings:
        salt.utils.versions.warn_until_date(
            datetime.datetime(2000, 1, 2),
            "Deprecation Message!",
            _current_date=_current_date,
        )
        assert "Deprecation Message!" == str(recorded_warnings[0].message)

    # Test warning with date as a string
    with warnings.catch_warnings(record=True) as recorded_warnings:
        salt.utils.versions.warn_until_date(
            "20000102", "Deprecation Message!", _current_date=_current_date
        )
        assert "Deprecation Message!" == str(recorded_warnings[0].message)

    # the deprecation warning is not issued because we passed
    # _dont_call_warning
    with warnings.catch_warnings(record=True) as recorded_warnings:
        salt.utils.versions.warn_until_date(
            "20000102",
            "Deprecation Message!",
            _dont_call_warnings=True,
            _current_date=_current_date,
        )
        assert len(recorded_warnings) == 0

    # Let's test for RuntimeError raise
    with pytest.raises(
        RuntimeError,
        match=(
            r"Deprecation Message! This warning\(now exception\) triggered on "
            r"filename \'(.*)test_versions.py\', line number ([\d]+), is "
            r"supposed to be shown until ([\d-]+). Today is ([\d-]+). "
            r"Please remove the warning."
        ),
    ):
        salt.utils.versions.warn_until_date("20000101", "Deprecation Message!")

    # Even though we're calling warn_until_date, we pass _dont_call_warnings
    # because we're only after the RuntimeError
    with pytest.raises(
        RuntimeError,
        match=(
            r"Deprecation Message! This warning\(now exception\) triggered on "
            r"filename \'(.*)test_versions.py\', line number ([\d]+), is "
            r"supposed to be shown until ([\d-]+). Today is ([\d-]+). "
            r"Please remove the warning."
        ),
    ):
        salt.utils.versions.warn_until_date(
            "20000101",
            "Deprecation Message!",
            _dont_call_warnings=True,
            _current_date=_current_date,
        )


def test_warn_until_date_bad_strptime_format():
    # We *always* want *all* warnings thrown on this module
    warnings.filterwarnings("always", "", DeprecationWarning, __name__)

    # Let's test for RuntimeError raise
    with pytest.raises(
        ValueError, match="time data '0022' does not match format '%Y%m%d'"
    ):
        salt.utils.versions.warn_until_date("0022", "Deprecation Message!")
