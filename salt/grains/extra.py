# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

# Import third party libs
import logging

# Import python libs
import os

# Import salt libs
import salt.utils.data
import salt.utils.files
import salt.utils.platform
import salt.utils.yaml

__proxyenabled__ = ["*"]
log = logging.getLogger(__name__)


def shell():
    """
    Return the default shell to use on this system
    """
    # Provides:
    #   shell
    if salt.utils.platform.is_windows():
        env_var = "COMSPEC"
        default = r"C:\Windows\system32\cmd.exe"
    else:
        env_var = "SHELL"
        default = "/bin/sh"

    return {"shell": os.environ.get(env_var, default)}


def config():
    """
    Return the grains set in the grains file
    """
    if "conf_file" not in __opts__:
        return {}
    if os.path.isdir(__opts__["conf_file"]):
        if salt.utils.platform.is_proxy():
            gfn = os.path.join(
                __opts__["conf_file"], "proxy.d", __opts__["id"], "grains"
            )
        else:
            gfn = os.path.join(__opts__["conf_file"], "grains")
    else:
        if salt.utils.platform.is_proxy():
            gfn = os.path.join(
                os.path.dirname(__opts__["conf_file"]),
                "proxy.d",
                __opts__["id"],
                "grains",
            )
        else:
            gfn = os.path.join(os.path.dirname(__opts__["conf_file"]), "grains")
    if os.path.isfile(gfn):
        log.debug("Loading static grains from %s", gfn)
        with salt.utils.files.fopen(gfn, "rb") as fp_:
            try:
                return salt.utils.data.decode(salt.utils.yaml.safe_load(fp_))
            except Exception:  # pylint: disable=broad-except
                log.warning("Bad syntax in grains file! Skipping.")
                return {}
    return {}
