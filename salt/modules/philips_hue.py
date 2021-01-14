# -*- coding: utf-8 -*-
#
# Copyright 2015 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Philips HUE lamps module for proxy.

.. versionadded:: 2015.8.3
"""

from __future__ import absolute_import, print_function, unicode_literals

import sys

__virtualname__ = "hue"
__proxyenabled__ = ["philips_hue"]


def _proxy():
    """
    Get proxy.
    """
    return __proxy__


def __virtual__():
    """
    Start the Philips HUE only for proxies.
    """
    if not _proxy():
        return False

    def _mkf(cmd_name, doc):
        """
        Nested function to help move proxy functions into sys.modules
        """

        def _cmd(*args, **kw):
            """
            Call commands in proxy
            """
            proxyfn = "philips_hue." + cmd_name
            return __proxy__[proxyfn](*args, **kw)

        return _cmd

    import salt.proxy.philips_hue as hue

    for method in dir(hue):
        if method.startswith("call_"):
            setattr(
                sys.modules[__name__],
                method[5:],
                _mkf(method, getattr(hue, method).__doc__),
            )
    del hue

    return _proxy() and __virtualname__ or False
