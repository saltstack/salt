# -*- coding: utf-8 -*-
'''
    :copyright: © 2017 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    salt.utils.versions
    ~~~~~~~~~~~~~~~~~~~

    Version parsing based on distutils.version which works under python 3
    because on python 3 you can no longer compare strings against integers.
'''

# Import pytohn libs
from __future__ import absolute_import
# pylint: disable=blacklisted-module
from distutils.version import StrictVersion as _StrictVersion
from distutils.version import LooseVersion as _LooseVersion
# pylint: enable=blacklisted-module

# Import 3rd-party libs
import salt.ext.six as six


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
