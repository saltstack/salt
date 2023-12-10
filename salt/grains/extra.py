import glob
import logging
import os

import salt.utils
import salt.utils.data
import salt.utils.files
import salt.utils.path
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


def __secure_boot(efivars_dir):
    """Detect if secure-boot is enabled."""
    enabled = False
    sboot = glob.glob(os.path.join(efivars_dir, "SecureBoot-*/data"))
    if len(sboot) == 1:
        # The minion is usually running as a privileged user, but is
        # not the case for the master.  Seems that the master can also
        # pick the grains, and this file can only be readed by "root"
        try:
            with salt.utils.files.fopen(sboot[0], "rb") as fd:
                enabled = fd.read()[-1:] == b"\x01"
        except PermissionError:
            pass
    return enabled


def uefi():
    """Populate UEFI grains."""
    efivars_dir = next(
        filter(os.path.exists, ["/sys/firmware/efi/efivars", "/sys/firmware/efi/vars"]),
        None,
    )
    grains = {
        "efi": bool(efivars_dir),
        "efi-secure-boot": __secure_boot(efivars_dir) if efivars_dir else False,
    }

    return grains


def transactional():
    """Determine if the system is transactional."""
    return {"transactional": bool(salt.utils.path.which("transactional-update"))}
