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
Execution module to upgrade Cisco NX-OS Switches.

.. versionadded:: 3001

This module supports execution using a Proxy Minion or Native Minion:
    1) Proxy Minion: Connect over SSH or NX-API HTTP(S).
       See :mod:`salt.proxy.nxos <salt.proxy.nxos>` for proxy minion setup details.
    2) Native Minion: Connect over NX-API Unix Domain Socket (UDS).
       Install the minion inside the GuestShell running on the NX-OS device.

:maturity:   new
:platform:   nxos
:codeauthor: Michael G Wiebe

.. note::

    To use this module over remote NX-API the feature must be enabled on the
    NX-OS device by executing ``feature nxapi`` in configuration mode.

    This is not required for NX-API over UDS.

    Configuration example:

    .. code-block:: bash

        switch# conf t
        switch(config)# feature nxapi

    To check that NX-API is properly enabled, execute ``show nxapi``.

    Output example:

    .. code-block:: bash

        switch# show nxapi
        nxapi enabled
        HTTPS Listen on port 443
"""

import ast
import logging
import re
import time

from salt.exceptions import CommandExecutionError, NxosError

__virtualname__ = "nxos"
__virtual_aliases__ = ("nxos_upgrade",)

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def check_upgrade_impact(system_image, kickstart_image=None, issu=True, **kwargs):
    """
    Display upgrade impact information without actually upgrading the device.

    system_image (Mandatory Option)
        Path on bootflash: to system image upgrade file.

    kickstart_image
        Path on bootflash: to kickstart image upgrade file.
        (Not required if using combined system/kickstart image file)
        Default: None

    issu
        In Service Software Upgrade (non-disruptive). When True,
        the upgrade will abort if issu is not possible.
        When False: Force (disruptive) Upgrade/Downgrade.
        Default: True

    timeout
        Timeout in seconds for long running 'install all' impact command.
        Default: 900

    error_pattern
        Use the option to pass in a regular expression to search for in the
        output of the 'install all impact' command that indicates an error
        has occurred.  This option is only used when proxy minion connection
        type is ssh and otherwise ignored.

    .. code-block:: bash

        salt 'n9k' nxos.check_upgrade_impact system_image=nxos.9.2.1.bin
        salt 'n7k' nxos.check_upgrade_impact system_image=n7000-s2-dk9.8.1.1.bin \\
            kickstart_image=n7000-s2-kickstart.8.1.1.bin issu=False
    """
    # Input Validation
    if not isinstance(issu, bool):
        return "Input Error: The [issu] parameter must be either True or False"

    si = system_image
    ki = kickstart_image
    dev = "bootflash"
    cmd = "terminal dont-ask ; show install all impact"

    if ki is not None:
        cmd = cmd + " kickstart {0}:{1} system {0}:{2}".format(dev, ki, si)
    else:
        cmd = cmd + f" nxos {dev}:{si}"

    if issu and ki is None:
        cmd = cmd + " non-disruptive"

    log.info("Check upgrade impact using command: '%s'", cmd)
    kwargs.update({"timeout": kwargs.get("timeout", 900)})
    error_pattern_list = [
        "Another install procedure may be in progress",
        "Pre-upgrade check failed",
    ]
    kwargs.update({"error_pattern": error_pattern_list})

    # Execute Upgrade Impact Check
    try:
        impact_check = __salt__["nxos.sendline"](cmd, **kwargs)
    except CommandExecutionError as e:
        impact_check = ast.literal_eval(e.message)
    return _parse_upgrade_data(impact_check)


def upgrade(system_image, kickstart_image=None, issu=True, **kwargs):
    """
    Upgrade NX-OS switch.

    system_image (Mandatory Option)
        Path on bootflash: to system image upgrade file.

    kickstart_image
        Path on bootflash: to kickstart image upgrade file.
        (Not required if using combined system/kickstart image file)
        Default: None

    issu
        Set this option to True when an In Service Software Upgrade or
        non-disruptive upgrade is required. The upgrade will abort if issu is
        not possible.
        Default: True

    timeout
        Timeout in seconds for long running 'install all' upgrade command.
        Default: 900

    error_pattern
        Use the option to pass in a regular expression to search for in the
        output of the 'install all upgrade command that indicates an error
        has occurred.  This option is only used when proxy minion connection
        type is ssh and otherwise ignored.

    .. code-block:: bash

        salt 'n9k' nxos.upgrade system_image=nxos.9.2.1.bin
        salt 'n7k' nxos.upgrade system_image=n7000-s2-dk9.8.1.1.bin \\
            kickstart_image=n7000-s2-kickstart.8.1.1.bin issu=False
    """
    # Input Validation
    if not isinstance(issu, bool):
        return "Input Error: The [issu] parameter must be either True or False"

    impact = None
    upgrade = None
    maxtry = 60
    for attempt in range(1, maxtry):
        # Gather impact data first.  It's possible to loose upgrade data
        # when the switch reloads or switches over to the inactive supervisor.
        # The impact data will be used if data being collected during the
        # upgrade is lost.
        if impact is None:
            log.info("Gathering impact data")
            impact = check_upgrade_impact(system_image, kickstart_image, issu, **kwargs)
            if impact["installing"]:
                log.info("Another show impact in progress... wait and retry")
                time.sleep(30)
                continue
            # If we are upgrading from a system running a separate system and
            # kickstart image to a combined image or vice versa then the impact
            # check will return a syntax error as it's not supported.
            # Skip the impact check in this case and attempt the upgrade.
            if impact["invalid_command"]:
                impact = False
                continue
            log.info("Impact data gathered:\n%s", impact)

            # Check to see if conditions are sufficent to return the impact
            # data and not proceed with the actual upgrade.
            #
            # Impact data indicates the upgrade or downgrade will fail
            if impact["error_data"]:
                return impact
            # Requested ISSU but ISSU is not possible
            if issu and not impact["upgrade_non_disruptive"]:
                impact["error_data"] = impact["upgrade_data"]
                return impact
            # Impact data indicates a failure and no module_data collected
            if not impact["succeeded"] and not impact["module_data"]:
                impact["error_data"] = impact["upgrade_data"]
                return impact
            # Impact data indicates switch already running desired image
            if not impact["upgrade_required"]:
                impact["succeeded"] = True
                return impact
        # If we get here, impact data indicates upgrade is needed.
        upgrade = _upgrade(system_image, kickstart_image, issu, **kwargs)
        if upgrade["installing"]:
            log.info("Another install is in progress... wait and retry")
            time.sleep(30)
            continue
        # If the issu option is False and this upgrade request includes a
        # kickstart image then the 'force' option is used.  This option is
        # only available in certain image sets.
        if upgrade["invalid_command"]:
            log_msg = "The [issu] option was set to False for this upgrade."
            log_msg = log_msg + " Attempt was made to ugrade using the force"
            log_msg = log_msg + " keyword which is not supported in this"
            log_msg = log_msg + " image.  Set [issu=True] and re-try."
            upgrade["upgrade_data"] = log_msg
            break
        break

    # Check for errors and return upgrade result:
    if upgrade["backend_processing_error"]:
        # This means we received a backend processing error from the transport
        # and lost the upgrade data.  This also indicates that the upgrade
        # is in progress so use the impact data for logging purposes.
        impact["upgrade_in_progress"] = True
        return impact
    return upgrade


def _upgrade(system_image, kickstart_image, issu, **kwargs):
    """
    Helper method that does the heavy lifting for upgrades.
    """
    si = system_image
    ki = kickstart_image
    dev = "bootflash"
    cmd = "terminal dont-ask ; install all"

    if ki is None:
        logmsg = "Upgrading device using combined system/kickstart image."
        logmsg += f"\nSystem Image: {si}"
        cmd = cmd + f" nxos {dev}:{si}"
        if issu:
            cmd = cmd + " non-disruptive"
    else:
        logmsg = "Upgrading device using separate system/kickstart images."
        logmsg += f"\nSystem Image: {si}"
        logmsg += f"\nKickstart Image: {ki}"
        if not issu:
            log.info("Attempting upgrade using force option")
            cmd = cmd + " force"
        cmd = cmd + " kickstart {0}:{1} system {0}:{2}".format(dev, ki, si)

    if issu:
        logmsg += "\nIn Service Software Upgrade/Downgrade (non-disruptive) requested."
    else:
        logmsg += "\nDisruptive Upgrade/Downgrade requested."

    log.info(logmsg)
    log.info("Begin upgrade using command: '%s'", cmd)

    kwargs.update({"timeout": kwargs.get("timeout", 900)})
    error_pattern_list = ["Another install procedure may be in progress"]
    kwargs.update({"error_pattern": error_pattern_list})

    # Begin Actual Upgrade
    try:
        upgrade_result = __salt__["nxos.sendline"](cmd, **kwargs)
    except CommandExecutionError as e:
        upgrade_result = ast.literal_eval(e.message)
    except NxosError as e:
        if re.search("Code: 500", e.message):
            upgrade_result = e.message
        else:
            upgrade_result = ast.literal_eval(e.message)
    return _parse_upgrade_data(upgrade_result)


def _parse_upgrade_data(data):
    """
    Helper method to parse upgrade data from the NX-OS device.
    """
    upgrade_result = {}
    upgrade_result["upgrade_data"] = None
    upgrade_result["succeeded"] = False
    upgrade_result["upgrade_required"] = False
    upgrade_result["upgrade_non_disruptive"] = False
    upgrade_result["upgrade_in_progress"] = False
    upgrade_result["installing"] = False
    upgrade_result["module_data"] = {}
    upgrade_result["error_data"] = None
    upgrade_result["backend_processing_error"] = False
    upgrade_result["invalid_command"] = False

    # Error handling
    if isinstance(data, str) and re.search("Code: 500", data):
        log.info("Detected backend processing error")
        upgrade_result["error_data"] = data
        upgrade_result["backend_processing_error"] = True
        return upgrade_result

    if isinstance(data, dict):
        if "code" in data and data["code"] == "400":
            log.info("Detected client error")
            upgrade_result["error_data"] = data["cli_error"]

            if re.search("install.*may be in progress", data["cli_error"]):
                log.info("Detected install in progress...")
                upgrade_result["installing"] = True

            if re.search("Invalid command", data["cli_error"]):
                log.info("Detected invalid command...")
                upgrade_result["invalid_command"] = True
        else:
            # If we get here then it's likely we lost access to the device
            # but the upgrade succeeded.  We lost the actual upgrade data so
            # set the flag such that impact data is used instead.
            log.info("Probable backend processing error")
            upgrade_result["backend_processing_error"] = True
        return upgrade_result

    # Get upgrade data for further parsing
    # Case 1: Command terminal dont-ask returns empty {} that we don't need.
    if isinstance(data, list) and len(data) == 2:
        data = data[1]
    # Case 2: Command terminal dont-ask does not get included.
    if isinstance(data, list) and len(data) == 1:
        data = data[0]

    log.info("Parsing NX-OS upgrade data")
    upgrade_result["upgrade_data"] = data
    for line in data.split("\n"):

        log.info("Processing line: (%s)", line)

        # Check to see if upgrade is disruptive or non-disruptive
        if re.search(r"non-disruptive", line):
            log.info("Found non-disruptive line")
            upgrade_result["upgrade_non_disruptive"] = True

        # Example:
        # Module  Image  Running-Version(pri:alt)  New-Version  Upg-Required
        # 1       nxos   7.0(3)I7(5a)              7.0(3)I7(5a)        no
        # 1       bios   v07.65(09/04/2018)        v07.64(05/16/2018)  no
        mo = re.search(r"(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(yes|no)", line)
        if mo:
            log.info("Matched Module Running/New Version Upg-Req Line")
            bk = "module_data"  # base key
            g1 = mo.group(1)
            g2 = mo.group(2)
            g3 = mo.group(3)
            g4 = mo.group(4)
            g5 = mo.group(5)
            mk = f"module {g1}:image {g2}"  # module key
            upgrade_result[bk][mk] = {}
            upgrade_result[bk][mk]["running_version"] = g3
            upgrade_result[bk][mk]["new_version"] = g4
            if g5 == "yes":
                upgrade_result["upgrade_required"] = True
                upgrade_result[bk][mk]["upgrade_required"] = True
            continue

        # The following lines indicate a successfull upgrade.
        if re.search(r"Install has been successful", line):
            log.info("Install successful line")
            upgrade_result["succeeded"] = True
            continue

        if re.search(r"Finishing the upgrade, switch will reboot in", line):
            log.info("Finishing upgrade line")
            upgrade_result["upgrade_in_progress"] = True
            continue

        if re.search(r"Switch will be reloaded for disruptive upgrade", line):
            log.info("Switch will be reloaded line")
            upgrade_result["upgrade_in_progress"] = True
            continue

        if re.search(r"Switching over onto standby", line):
            log.info("Switching over onto standby line")
            upgrade_result["upgrade_in_progress"] = True
            continue

    return upgrade_result
