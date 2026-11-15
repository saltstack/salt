#!/usr/bin/env python
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""The Tornado web server and tools."""
# pylint: skip-file

from __future__ import absolute_import, division, print_function

# version is a human-readable version number.

# version_info is a four-tuple for programmatic comparison. The first
# three numbers are the components of the version number.  The fourth
# is zero for an official release, positive for a development branch,
# or negative for a release candidate or beta (after the base version
# number has been incremented)


# The bundled code is based on Tornado 4.5.3 (its API is still that of 4.5.3)
# and has had the security fixes made in Tornado releases up to 6.6.1
# backported to it. The version below reports the release those fixes are
# current with, so that scanners and the ``Server`` header describe the
# security status of the code accurately.
version = "6.6.1"
version_info = (6, 6, 1, 0)
