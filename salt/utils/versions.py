"""
    salt.utils.versions
    ~~~~~~~~~~~~~~~~~~~

    Version parsing based on `packaging.version` and `looseversion.LooseVersion`
    which works under python 3 because on python 3 you can no longer compare
    strings against integers.
"""

import datetime
import inspect
import logging
import numbers
import os
import sys
import warnings

import looseversion
import packaging.version

import salt.version

log = logging.getLogger(__name__)


class Version(packaging.version.Version):
    def __lt__(self, other):
        if isinstance(other, str):
            other = Version(other)
        return super().__lt__(other)

    def __le__(self, other):
        if isinstance(other, str):
            other = Version(other)
        return super().__le__(other)

    def __eq__(self, other):
        if isinstance(other, str):
            other = Version(other)
        return super().__eq__(other)

    def __ge__(self, other):
        if isinstance(other, str):
            other = Version(other)
        return super().__ge__(other)

    def __gt__(self, other):
        if isinstance(other, str):
            other = Version(other)
        return super().__gt__(other)

    def __ne__(self, other):
        if isinstance(other, str):
            other = Version(other)
        return super().__ne__(other)


class StrictVersion(Version):
    def __init__(self, *args, **kwargs):
        warn_until(
            3008,
            f"'{__name__}.StrictVersion' is no longer a subclass of "
            "'distutils.versions.StrictVersion'. It's usage has been "
            "deprecated and should no longer be used. Please switch to "
            f"'{__name__}.Version' which is a subclass of "
            f"'packaging.version.Version'. '{__name__}.StrictVersion' will "
            "be removed in {version}.",
        )
        super().__init__(*args, **kwargs)


class LooseVersion(looseversion.LooseVersion):
    def parse(self, vstring):
        super().parse(vstring)
        # Convert every part of the version to string in order to be able to compare
        self._str_version = [
            str(vp).zfill(8) if isinstance(vp, int) else vp for vp in self.version
        ]

    def _cmp(self, other):
        if isinstance(other, str):
            other = LooseVersion(other)

        string_in_version = False
        for part in self.version + other.version:
            if not isinstance(part, int):
                string_in_version = True
                break

        if string_in_version is False:
            return super()._cmp(other)

        # If we reached this far, it means at least a part of the version contains a string
        # In python 3, strings and integers are not comparable
        if self._str_version == other._str_version:
            return 0
        if self._str_version < other._str_version:
            return -1
        if self._str_version > other._str_version:
            return 1


def _format_warning(message, category, filename, lineno, line=None):
    """
    Replacement for warnings.formatwarning that disables the echoing of
    the 'line' parameter.
    """
    return f"{filename}:{lineno}: {category.__name__}: {message}\n"


def warn_until(
    version,
    message,
    category=DeprecationWarning,
    stacklevel=None,
    _version_info_=None,
    _dont_call_warnings=False,
):
    """
    Helper function to raise a warning, by default, a ``DeprecationWarning``,
    until the provided ``version``, after which, a ``RuntimeError`` will
    be raised to remind the developers to remove the warning because the
    target version has been reached.

    :param version: The version info or name after which the warning becomes a ``RuntimeError``.
                    For example ``(2019, 2)``, ``3000``, ``Hydrogen`` or an instance of
                    :class:`salt.version.SaltStackVersion` or :class:`salt.version.SaltVersion`.
    :param message: The warning message to be displayed.
    :param category: The warning class to be thrown, by default
                     ``DeprecationWarning``
    :param stacklevel: There should be no need to set the value of
                       ``stacklevel``. Salt should be able to do the right thing.
    :param _version_info_: In order to reuse this function for other SaltStack
                           projects, they need to be able to provide the
                           version info to compare to.
    :param _dont_call_warnings: This parameter is used just to get the
                                functionality until the actual error is to be
                                issued. When we're only after the salt version
                                checks to raise a ``RuntimeError``.
    """
    if isinstance(version, salt.version.SaltVersion):
        version = salt.version.SaltStackVersion(*version.info)
    elif isinstance(version, int):
        version = salt.version.SaltStackVersion(version)
    elif isinstance(version, tuple):
        version = salt.version.SaltStackVersion(*version)
    elif isinstance(version, str):
        if version.lower() not in salt.version.SaltStackVersion.LNAMES:
            raise RuntimeError(
                "Incorrect spelling for the release name in the warn_utils "
                "call. Expecting one of these release names: {}".format(
                    [vs.name for vs in salt.version.SaltVersionsInfo.versions()]
                )
            )
        version = salt.version.SaltStackVersion.from_name(version)
    elif not isinstance(version, salt.version.SaltStackVersion):
        raise RuntimeError(
            "The 'version' argument should be passed as a tuple, integer, string or "
            "an instance of 'salt.version.SaltVersion' or "
            "'salt.version.SaltStackVersion'."
        )

    if stacklevel is None:
        # Attribute the warning to the calling function, not to warn_until()
        stacklevel = 2

    if _version_info_ is None:
        _version_info_ = salt.version.__version_info__

    _version_ = salt.version.SaltStackVersion(*_version_info_)

    if _version_ >= version:
        caller = inspect.getframeinfo(sys._getframe(stacklevel - 1))
        deprecated_message = (
            "The warning triggered on filename '{filename}', line number "
            "{lineno}, is supposed to be shown until version "
            "{until_version} is released. Current version is now "
            "{salt_version}. Please remove the warning.".format(
                filename=caller.filename,
                lineno=caller.lineno,
                until_version=version.formatted_version,
                salt_version=_version_.formatted_version,
            )
        )
        if os.environ.get("RAISE_DEPRECATIONS_RUNTIME_ERRORS", "0") == "1":
            # We don't raise RuntimeError by default since that can break
            # users systems. We do however want to raise them in a CI context.
            raise RuntimeError(deprecated_message)
        # Otherwise, print the deprecated message to STDERR
        sys.stderr.write(f"\n{deprecated_message}\n")
        sys.stderr.flush()

    if _dont_call_warnings is False:
        warnings.warn(
            message.format(version=version.formatted_version),
            category,
            stacklevel=stacklevel,
        )


def warn_until_date(
    date,
    message,
    category=DeprecationWarning,
    stacklevel=None,
    _current_date=None,
    _dont_call_warnings=False,
):
    """
    Helper function to raise a warning, by default, a ``DeprecationWarning``,
    until the provided ``date``, after which, a ``RuntimeError`` will
    be raised to remind the developers to remove the warning because the
    target date has been reached.

    :param date: A ``datetime.date`` or ``datetime.datetime`` instance.
    :param message: The warning message to be displayed.
    :param category: The warning class to be thrown, by default
                     ``DeprecationWarning``
    :param stacklevel: There should be no need to set the value of
                       ``stacklevel``. Salt should be able to do the right thing.
    :param _dont_call_warnings: This parameter is used just to get the
                                functionality until the actual error is to be
                                issued. When we're only after the date
                                checks to raise a ``RuntimeError``.
    """
    _strptime_fmt = "%Y%m%d"
    if not isinstance(date, (str, datetime.date, datetime.datetime)):
        raise RuntimeError(
            "The 'date' argument should be passed as a 'datetime.date()' or "
            "'datetime.datetime()' objects or as string parserable by "
            "'datetime.datetime.strptime()' with the following format '{}'.".format(
                _strptime_fmt
            )
        )
    elif isinstance(date, str):
        date = datetime.datetime.strptime(date, _strptime_fmt)

    # We're really not interested in the time
    if isinstance(date, datetime.datetime):
        date = date.date()

    if stacklevel is None:
        # Attribute the warning to the calling function, not to warn_until_date()
        stacklevel = 2

    today = _current_date or datetime.datetime.utcnow().date()
    if today >= date:
        caller = inspect.getframeinfo(sys._getframe(stacklevel - 1))
        deprecated_message = (
            "{message} This warning(now exception) triggered on "
            "filename '{filename}', line number {lineno}, is "
            "supposed to be shown until {date}. Today is {today}. "
            "Please remove the warning.".format(
                message=message.format(date=date.isoformat(), today=today.isoformat()),
                filename=caller.filename,
                lineno=caller.lineno,
                date=date.isoformat(),
                today=today.isoformat(),
            ),
        )
        if os.environ.get("RAISE_DEPRECATIONS_RUNTIME_ERRORS", "0") == "1":
            # We don't raise RuntimeError by default since that can break
            # users systems. We do however want to raise them in a CI context.
            raise RuntimeError(deprecated_message)
        # Otherwise, print the deprecated message to STDERR
        sys.stderr.write(f"\n{deprecated_message}\n")
        sys.stderr.flush()

    if _dont_call_warnings is False:
        warnings.warn(
            message.format(date=date.isoformat(), today=today.isoformat()),
            category,
            stacklevel=stacklevel,
        )


def kwargs_warn_until(
    kwargs,
    version,
    category=DeprecationWarning,
    stacklevel=None,
    _version_info_=None,
    _dont_call_warnings=False,
):
    """
    Helper function to raise a warning (by default, a ``DeprecationWarning``)
    when unhandled keyword arguments are passed to function, until the
    provided ``version_info``, after which, a ``RuntimeError`` will be raised
    to remind the developers to remove the ``**kwargs`` because the target
    version has been reached.
    This function is used to help deprecate unused legacy ``**kwargs`` that
    were added to function parameters lists to preserve backwards compatibility
    when removing a parameter. See
    :ref:`the deprecation development docs <deprecations>`
    for the modern strategy for deprecating a function parameter.

    :param kwargs: The caller's ``**kwargs`` argument value (a ``dict``).
    :param version: The version info or name after which the warning becomes a
                    ``RuntimeError``. For example ``(0, 17)`` or ``Hydrogen``
                    or an instance of :class:`salt.version.SaltStackVersion`.
    :param category: The warning class to be thrown, by default
                     ``DeprecationWarning``
    :param stacklevel: There should be no need to set the value of
                       ``stacklevel``. Salt should be able to do the right thing.
    :param _version_info_: In order to reuse this function for other SaltStack
                           projects, they need to be able to provide the
                           version info to compare to.
    :param _dont_call_warnings: This parameter is used just to get the
                                functionality until the actual error is to be
                                issued. When we're only after the salt version
                                checks to raise a ``RuntimeError``.
    """
    if not isinstance(version, (tuple, str, salt.version.SaltStackVersion)):
        raise RuntimeError(
            "The 'version' argument should be passed as a tuple, string or "
            "an instance of 'salt.version.SaltStackVersion'."
        )
    elif isinstance(version, tuple):
        version = salt.version.SaltStackVersion(*version)
    elif isinstance(version, str):
        version = salt.version.SaltStackVersion.from_name(version)

    if stacklevel is None:
        # Attribute the warning to the calling function,
        # not to kwargs_warn_until() or warn_until()
        stacklevel = 3

    if _version_info_ is None:
        _version_info_ = salt.version.__version_info__

    _version_ = salt.version.SaltStackVersion(*_version_info_)

    if kwargs or _version_.info >= version.info:
        arg_names = ", ".join(f"'{key}'" for key in kwargs)
        warn_until(
            version,
            message=(
                "The following parameter(s) have been deprecated and "
                "will be removed in '{}': {}.".format(version.string, arg_names)
            ),
            category=category,
            stacklevel=stacklevel,
            _version_info_=_version_.info,
            _dont_call_warnings=_dont_call_warnings,
        )


def version_cmp(pkg1, pkg2, ignore_epoch=False):
    """
    Compares two version strings using `LooseVersion`. This
    is a fallback for providers which don't have a version comparison utility
    built into them.  Return -1 if version1 < version2, 0 if version1 ==
    version2, and 1 if version1 > version2. Return None if there was a problem
    making the comparison.
    """

    def normalize(x):
        return str(x).split(":", 1)[-1] if ignore_epoch else str(x)

    pkg1 = normalize(pkg1)
    pkg2 = normalize(pkg2)

    try:
        # pylint: disable=no-member
        if LooseVersion(pkg1) < LooseVersion(pkg2):
            return -1
        elif LooseVersion(pkg1) == LooseVersion(pkg2):
            return 0
        elif LooseVersion(pkg1) > LooseVersion(pkg2):
            return 1
    except Exception as exc:  # pylint: disable=broad-except
        log.exception(exc)
    return None


def compare(ver1="", oper="==", ver2="", cmp_func=None, ignore_epoch=False):
    """
    Compares two version numbers. Accepts a custom function to perform the
    cmp-style version comparison, otherwise uses version_cmp().
    """
    cmp_map = {"<": (-1,), "<=": (-1, 0), "==": (0,), ">=": (0, 1), ">": (1,)}
    if oper not in ("!=",) and oper not in cmp_map:
        log.error("Invalid operator '%s' for version comparison", oper)
        return False

    if cmp_func is None:
        cmp_func = version_cmp

    cmp_result = cmp_func(ver1, ver2, ignore_epoch=ignore_epoch)
    if cmp_result is None:
        return False

    # Check if integer/long
    if not isinstance(cmp_result, numbers.Integral):
        log.error("The version comparison function did not return an integer/long.")
        return False

    if oper == "!=":
        return cmp_result not in cmp_map["=="]
    else:
        # Gracefully handle cmp_result not in (-1, 0, 1).
        if cmp_result < -1:
            cmp_result = -1
        elif cmp_result > 1:
            cmp_result = 1

        return cmp_result in cmp_map[oper]


def check_boto_reqs(
    boto_ver=None, boto3_ver=None, botocore_ver=None, check_boto=True, check_boto3=True
):
    """
    Checks for the version of various required boto libs in one central location. Most
    boto states and modules rely on a single version of the boto, boto3, or botocore libs.
    However, some require newer versions of any of these dependencies. This function allows
    the module to pass in a version to override the default minimum required version.

    This function is useful in centralizing checks for ``__virtual__()`` functions in the
    various, and many, boto modules and states.

    boto_ver
        The minimum required version of the boto library. Defaults to ``2.0.0``.

    boto3_ver
        The minimum required version of the boto3 library. Defaults to ``1.2.6``.

    botocore_ver
        The minimum required version of the botocore library. Defaults to ``1.3.23``.

    check_boto
        Boolean defining whether or not to check for boto deps. This defaults to ``True`` as
        most boto modules/states rely on boto, but some do not.

    check_boto3
        Boolean defining whether or not to check for boto3 (and therefore botocore) deps.
        This defaults to ``True`` as most boto modules/states rely on boto3/botocore, but
        some do not.
    """
    if check_boto is True:
        try:
            # Late import so we can only load these for this function
            import boto

            has_boto = True
        except ImportError:
            has_boto = False

        if boto_ver is None:
            boto_ver = "2.0.0"

        if not has_boto or version_cmp(boto.__version__, boto_ver) == -1:
            return False, f"A minimum version of boto {boto_ver} is required."

    if check_boto3 is True:
        try:
            # Late import so we can only load these for this function
            import boto3
            import botocore

            has_boto3 = True
        except ImportError:
            has_boto3 = False

        # boto_s3_bucket module requires boto3 1.2.6 and botocore 1.3.23 for
        # idempotent ACL operations via the fix in https://github.com/boto/boto3/issues/390
        if boto3_ver is None:
            boto3_ver = "1.2.6"
        if botocore_ver is None:
            botocore_ver = "1.3.23"

        if not has_boto3 or version_cmp(boto3.__version__, boto3_ver) == -1:
            return (
                False,
                f"A minimum version of boto3 {boto3_ver} is required.",
            )
        elif version_cmp(botocore.__version__, botocore_ver) == -1:
            return (
                False,
                f"A minimum version of botocore {botocore_ver} is required",
            )

    return True
