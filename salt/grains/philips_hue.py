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
Static grains for the Philips HUE lamps

.. versionadded:: 2015.8.3
"""

__proxyenabled__ = ["philips_hue"]

__virtualname__ = "hue"


def __virtual__():
    if "proxy" not in __opts__:
        return False
    else:
        return __virtualname__


def kernel():
    return {"kernel": "RTOS"}


def os():
    return {"os": "FreeRTOS"}


def os_family():
    return {"os_family": "RTOS"}


def vendor():
    return {"vendor": "Philips"}


def product():
    return {"product": "HUE"}
