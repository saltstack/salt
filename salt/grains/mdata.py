"""
SmartOS Metadata grain provider

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils, salt.module.cmdmod
:platform:      SmartOS

.. versionadded:: 2017.7.0

"""

import logging
import os

import salt.modules.cmdmod
import salt.utils.dictupdate
import salt.utils.json
import salt.utils.path
import salt.utils.platform

__virtualname__ = "mdata"
__salt__ = {
    "cmd.run": salt.modules.cmdmod.run,
}

log = logging.getLogger(__name__)


def __virtual__():
    """
    Figure out if we need to be loaded
    """
    ## collect mdata grains in a SmartOS zone
    if salt.utils.platform.is_smartos_zone():
        return __virtualname__
    ## collect mdata grains in a LX zone
    if salt.utils.platform.is_linux() and "BrandZ virtual linux" in os.uname():
        return __virtualname__
    return False


def _user_mdata(mdata_list=None, mdata_get=None):
    """
    User Metadata
    """
    grains = {}

    if not mdata_list:
        mdata_list = salt.utils.path.which("mdata-list")

    if not mdata_get:
        mdata_get = salt.utils.path.which("mdata-get")

    if not mdata_list or not mdata_get:
        return grains

    for mdata_grain in __salt__["cmd.run"](
        mdata_list, ignore_retcode=True
    ).splitlines():
        if mdata_grain.startswith("ERROR:"):
            log.warning("mdata-list returned an error, skipping mdata grains.")
            continue
        mdata_value = __salt__["cmd.run"](
            f"{mdata_get} {mdata_grain}", ignore_retcode=True
        )

        if not mdata_grain.startswith("sdc:"):
            if "mdata" not in grains:
                grains["mdata"] = {}

            log.debug("found mdata entry %s with value %s", mdata_grain, mdata_value)
            mdata_grain = mdata_grain.replace("-", "_")
            mdata_grain = mdata_grain.replace(":", "_")
            grains["mdata"][mdata_grain] = mdata_value

    return grains


def _sdc_mdata(mdata_list=None, mdata_get=None):
    """
    SDC Metadata specified by there specs
    https://eng.joyent.com/mdata/datadict.html
    """
    grains = {}
    sdc_text_keys = [
        "uuid",
        "server_uuid",
        "datacenter_name",
        "hostname",
        "dns_domain",
        "alias",
    ]
    sdc_json_keys = [
        "resolvers",
        "nics",
        "routes",
    ]

    if not mdata_list:
        mdata_list = salt.utils.path.which("mdata-list")

    if not mdata_get:
        mdata_get = salt.utils.path.which("mdata-get")

    if not mdata_list or not mdata_get:
        return grains

    for mdata_grain in sdc_text_keys + sdc_json_keys:
        mdata_value = __salt__["cmd.run"](
            f"{mdata_get} sdc:{mdata_grain}", ignore_retcode=True
        )
        if mdata_value.startswith("ERROR:"):
            log.warning(
                "unable to read sdc:%s via mdata-get, mdata grain may be incomplete.",
                mdata_grain,
            )
            continue

        if not mdata_value.startswith("No metadata for "):
            if "mdata" not in grains:
                grains["mdata"] = {}
            if "sdc" not in grains["mdata"]:
                grains["mdata"]["sdc"] = {}

            log.debug(
                "found mdata entry sdc:%s with value %s", mdata_grain, mdata_value
            )
            mdata_grain = mdata_grain.replace("-", "_")
            mdata_grain = mdata_grain.replace(":", "_")
            if mdata_grain in sdc_json_keys:
                grains["mdata"]["sdc"][mdata_grain] = salt.utils.json.loads(mdata_value)
            else:
                grains["mdata"]["sdc"][mdata_grain] = mdata_value

    return grains


def mdata():
    """
    Provide grains from the SmartOS metadata
    """
    grains = {}
    mdata_list = salt.utils.path.which("mdata-list")
    mdata_get = salt.utils.path.which("mdata-get")

    grains = salt.utils.dictupdate.update(
        grains, _user_mdata(mdata_list, mdata_get), merge_lists=True
    )
    grains = salt.utils.dictupdate.update(
        grains, _sdc_mdata(mdata_list, mdata_get), merge_lists=True
    )

    return grains
