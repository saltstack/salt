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
        if six.PY3:
            # Convert every part of the version to string in order to be able to compare
            self.version = [str(vp) for vp in self.version]


class LooseVersion(_LooseVersion):

    def parse(self, vstring):
        _LooseVersion.parse(self, vstring)
        if six.PY3:
            # Convert every part of the version to string in order to be able to compare
            self.version = [str(vp) for vp in self.version]
