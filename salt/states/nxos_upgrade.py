# Copyright (c) 2018 Cisco and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Manage NX-OS System Image Upgrades.

.. versionadded:: 3001

:maturity:   new
:platform:   nxos
:codeauthor: Michael G Wiebe

For documentation on setting up the nxos proxy minion look in the documentation
for :mod:`salt.proxy.nxos<salt.proxy.nxos>`.
"""

import logging

__virtualname__ = "nxos"
__virtual_aliases__ = ("nxos_upgrade",)

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def image_running(name, system_image, kickstart_image=None, issu=True, **kwargs):
    """
    Ensure the NX-OS system image is running on the device.

    name
        Name of the salt state task

    system_image
        Name of the system image file on bootflash:

    kickstart_image
        Name of the kickstart image file on bootflash:
        This is not needed if the system_image is a combined system and
        kickstart image
        Default: None

    issu
        Ensure the correct system is running on the device using an in service
        software upgrade, or force a disruptive upgrade by setting the option
        to False.
        Default: False

    timeout
        Timeout in seconds for long running 'install all' upgrade command.
        Default: 900

    Examples:

    .. code-block:: yaml

        upgrade_software_image_n9k:
          nxos.image_running:
            - name: Ensure nxos.7.0.3.I7.5a.bin is running
            - system_image: nxos.7.0.3.I7.5a.bin
            - issu: True

        upgrade_software_image_n7k:
          nxos.image_running:
            - name: Ensure n7000-s2-kickstart.8.0.1.bin is running
            - kickstart_image: n7000-s2-kickstart.8.0.1.bin
            - system_image: n7000-s2-dk9.8.0.1.bin
            - issu: False
    """
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    if kickstart_image is None:
        upgrade = __salt__["nxos.upgrade"](
            system_image=system_image, issu=issu, **kwargs
        )
    else:
        upgrade = __salt__["nxos.upgrade"](
            system_image=system_image,
            kickstart_image=kickstart_image,
            issu=issu,
            **kwargs,
        )

    if upgrade["upgrade_in_progress"]:
        ret["result"] = upgrade["upgrade_in_progress"]
        ret["changes"] = upgrade["module_data"]
        ret["comment"] = "NX-OS Device Now Being Upgraded - See Change Details Below"
    elif upgrade["succeeded"]:
        ret["result"] = upgrade["succeeded"]
        ret["comment"] = f"NX-OS Device Running Image: {_version_info()}"
    else:
        ret["comment"] = "Upgrade Failed: {}.".format(upgrade["error_data"])

    return ret


def _version_info():
    """
    Helper method to return running image version
    """
    if "NXOS" in __grains__["nxos"]["software"]:
        return __grains__["nxos"]["software"]["NXOS"]
    elif "kickstart" in __grains__["nxos"]["software"]:
        return __grains__["nxos"]["software"]["kickstart"]
    else:
        return "Unable to detect sofware version"
