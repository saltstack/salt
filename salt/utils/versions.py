# -*- coding: utf-8 -*-
'''
    :copyright: Copyright 2017 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    salt.utils.versions
    ~~~~~~~~~~~~~~~~~~~

    Version parsing based on distutils.version which works under python 3
    because on python 3 you can no longer compare strings against integers.
'''

# Import Python libs
from __future__ import absolute_import
import logging
import numbers
import sys
import warnings
# pylint: disable=blacklisted-module
from distutils.version import StrictVersion as _StrictVersion
from distutils.version import LooseVersion as _LooseVersion
# pylint: enable=blacklisted-module

# Import Salt libs
import salt.version

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


class StrictVersion(_StrictVersion):
    def parse(self, vstring):
        _StrictVersion.parse(self, vstring)

    def _cmp(self, other):
        if isinstance(other, six.string_types):
            other = StrictVersion(other)
        return _StrictVersion._cmp(self, other)


class LooseVersion(_LooseVersion):

    def parse(self, vstring):
        _LooseVersion.parse(self, vstring)

        if six.PY3:
            # Convert every part of the version to string in order to be able to compare
            self._str_version = [
                str(vp).zfill(8) if isinstance(vp, int) else vp for vp in self.version]

    if six.PY3:
        def _cmp(self, other):
            if isinstance(other, six.string_types):
                other = LooseVersion(other)

            string_in_version = False
            for part in self.version + other.version:
                if not isinstance(part, int):
                    string_in_version = True
                    break

            if string_in_version is False:
                return _LooseVersion._cmp(self, other)

            # If we reached this far, it means at least a part of the version contains a string
            # In python 3, strings and integers are not comparable
            if self._str_version == other._str_version:
                return 0
            if self._str_version < other._str_version:
                return -1
            if self._str_version > other._str_version:
                return 1


def warn_until(version,
               message,
               category=DeprecationWarning,
               stacklevel=None,
               _version_info_=None,
               _dont_call_warnings=False):
    '''
    Helper function to raise a warning, by default, a ``DeprecationWarning``,
    until the provided ``version``, after which, a ``RuntimeError`` will
    be raised to remind the developers to remove the warning because the
    target version has been reached.

    :param version: The version info or name after which the warning becomes a
                    ``RuntimeError``. For example ``(0, 17)`` or ``Hydrogen``
                    or an instance of :class:`salt.version.SaltStackVersion`.
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
    '''
    if not isinstance(version, (tuple,
                                six.string_types,
                                salt.version.SaltStackVersion)):
        raise RuntimeError(
            'The \'version\' argument should be passed as a tuple, string or '
            'an instance of \'salt.version.SaltStackVersion\'.'
        )
    elif isinstance(version, tuple):
        version = salt.version.SaltStackVersion(*version)
    elif isinstance(version, six.string_types):
        version = salt.version.SaltStackVersion.from_name(version)

    if stacklevel is None:
        # Attribute the warning to the calling function, not to warn_until()
        stacklevel = 2

    if _version_info_ is None:
        _version_info_ = salt.version.__version_info__

    _version_ = salt.version.SaltStackVersion(*_version_info_)

    if _version_ >= version:
        import inspect
        caller = inspect.getframeinfo(sys._getframe(stacklevel - 1))
        raise RuntimeError(
            'The warning triggered on filename \'{filename}\', line number '
            '{lineno}, is supposed to be shown until version '
            '{until_version} is released. Current version is now '
            '{salt_version}. Please remove the warning.'.format(
                filename=caller.filename,
                lineno=caller.lineno,
                until_version=version.formatted_version,
                salt_version=_version_.formatted_version
            ),
        )

    if _dont_call_warnings is False:
        def _formatwarning(message,
                           category,
                           filename,
                           lineno,
                           line=None):  # pylint: disable=W0613
            '''
            Replacement for warnings.formatwarning that disables the echoing of
            the 'line' parameter.
            '''
            return '{0}:{1}: {2}: {3}\n'.format(
                filename, lineno, category.__name__, message
            )
        saved = warnings.formatwarning
        warnings.formatwarning = _formatwarning
        warnings.warn(
            message.format(version=version.formatted_version),
            category,
            stacklevel=stacklevel
        )
        warnings.formatwarning = saved


def kwargs_warn_until(kwargs,
                      version,
                      category=DeprecationWarning,
                      stacklevel=None,
                      _version_info_=None,
                      _dont_call_warnings=False):
    '''
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
    '''
    if not isinstance(version, (tuple,
                                six.string_types,
                                salt.version.SaltStackVersion)):
        raise RuntimeError(
            'The \'version\' argument should be passed as a tuple, string or '
            'an instance of \'salt.version.SaltStackVersion\'.'
        )
    elif isinstance(version, tuple):
        version = salt.version.SaltStackVersion(*version)
    elif isinstance(version, six.string_types):
        version = salt.version.SaltStackVersion.from_name(version)

    if stacklevel is None:
        # Attribute the warning to the calling function,
        # not to kwargs_warn_until() or warn_until()
        stacklevel = 3

    if _version_info_ is None:
        _version_info_ = salt.version.__version_info__

    _version_ = salt.version.SaltStackVersion(*_version_info_)

    if kwargs or _version_.info >= version.info:
        arg_names = ', '.join('\'{0}\''.format(key) for key in kwargs)
        warn_until(
            version,
            message='The following parameter(s) have been deprecated and '
                    'will be removed in \'{0}\': {1}.'.format(version.string,
                                                              arg_names),
            category=category,
            stacklevel=stacklevel,
            _version_info_=_version_.info,
            _dont_call_warnings=_dont_call_warnings
        )


def version_cmp(pkg1, pkg2, ignore_epoch=False):
    '''
    Compares two version strings using salt.utils.versions.LooseVersion. This
    is a fallback for providers which don't have a version comparison utility
    built into them.  Return -1 if version1 < version2, 0 if version1 ==
    version2, and 1 if version1 > version2. Return None if there was a problem
    making the comparison.
    '''
    normalize = lambda x: str(x).split(':', 1)[-1] if ignore_epoch else str(x)
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
    except Exception as exc:
        log.exception(exc)
    return None


def compare(ver1='', oper='==', ver2='', cmp_func=None, ignore_epoch=False):
    '''
    Compares two version numbers. Accepts a custom function to perform the
    cmp-style version comparison, otherwise uses version_cmp().
    '''
    cmp_map = {'<': (-1,), '<=': (-1, 0), '==': (0,),
               '>=': (0, 1), '>': (1,)}
    if oper not in ('!=',) and oper not in cmp_map:
        log.error('Invalid operator \'%s\' for version comparison', oper)
        return False

    if cmp_func is None:
        cmp_func = version_cmp

    cmp_result = cmp_func(ver1, ver2, ignore_epoch=ignore_epoch)
    if cmp_result is None:
        return False

    # Check if integer/long
    if not isinstance(cmp_result, numbers.Integral):
        log.error('The version comparison function did not return an '
                  'integer/long.')
        return False

    if oper == '!=':
        return cmp_result not in cmp_map['==']
    else:
        # Gracefully handle cmp_result not in (-1, 0, 1).
        if cmp_result < -1:
            cmp_result = -1
        elif cmp_result > 1:
            cmp_result = 1

        return cmp_result in cmp_map[oper]
