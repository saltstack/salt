"""
Virtual machine image management tools
"""

import logging
import os
import shutil
import tempfile
import uuid

import salt.config
import salt.crypt
import salt.syspaths
import salt.utils.cloud
import salt.utils.files

# Set up logging
log = logging.getLogger(__name__)

# Don't shadow built-in's.
__func_alias__ = {"apply_": "apply"}


def _file_or_content(file_):
    if os.path.exists(file_):
        with salt.utils.files.fopen(file_) as fic:
            return salt.utils.stringutils.to_unicode(fic.read())
    return file_


def prep_bootstrap(mpt):
    """
    Update and get the random script to a random place

    CLI Example:

    .. code-block:: bash

        salt '*' seed.prep_bootstrap /tmp

    """
    # Verify that the boostrap script is downloaded
    bs_ = __salt__["config.gather_bootstrap_script"]()
    fpd_ = os.path.join(mpt, "tmp", f"{uuid.uuid4()}")
    if not os.path.exists(fpd_):
        os.makedirs(fpd_)
    os.chmod(fpd_, 0o700)
    fp_ = os.path.join(fpd_, os.path.basename(bs_))
    # Copy script into tmp
    shutil.copy(bs_, fp_)
    tmppath = fpd_.replace(mpt, "")
    return fp_, tmppath


def _mount(path, ftype, root=None):
    mpt = None
    if ftype == "block":
        mpt = tempfile.mkdtemp()
        if not __salt__["mount.mount"](mpt, path):
            os.rmdir(mpt)
            return None
    elif ftype == "dir":
        return path
    elif ftype == "file":
        if "guestfs.mount" in __salt__:
            util = "guestfs"
        elif "qemu_nbd.init" in __salt__:
            util = "qemu_nbd"
        else:
            return None
        mpt = __salt__["mount.mount"](path, device=root, util=util)
        if not mpt:
            return None
    return mpt


def _umount(mpt, disk, ftype):
    if ftype == "block":
        __salt__["mount.umount"](mpt)
        os.rmdir(mpt)
    elif ftype == "file":
        util = None
        if "guestfs.mount" in __salt__:
            util = "guestfs"
        elif "qemu_nbd.init" in __salt__:
            util = "qemu_nbd"
        if util:
            __salt__["mount.umount"](mpt, device=disk, util=util)


def apply_(
    path,
    id_=None,
    config=None,
    approve_key=True,
    install=True,
    prep_install=False,
    pub_key=None,
    priv_key=None,
    mount_point=None,
):
    """
    Seed a location (disk image, directory, or block device) with the
    minion config, approve the minion's key, and/or install salt-minion.

    CLI Example:

    .. code-block:: bash

        salt 'minion' seed.apply path id [config=config_data] \\
                [gen_key=(true|false)] [approve_key=(true|false)] \\
                [install=(true|false)]

    path
        Full path to the directory, device, or disk image  on the target
        minion's file system.

    id
        Minion id with which to seed the path.

    config
        Minion configuration options. By default, the 'master' option is set to
        the target host's 'master'.

    approve_key
        Request a pre-approval of the generated minion key. Requires
        that the salt-master be configured to either auto-accept all keys or
        expect a signing request from the target host. Default: true.

    install
        Install salt-minion, if absent. Default: true.

    prep_install
        Prepare the bootstrap script, but don't run it. Default: false
    """
    stats = __salt__["file.stats"](path, follow_symlinks=True)
    if not stats:
        return f"{path} does not exist"
    ftype = stats["type"]
    path = stats["target"]
    log.debug("Mounting %s at %s", ftype, path)
    try:
        os.makedirs(path)
    except OSError:
        # The directory already exists
        pass

    mpt = _mount(path, ftype, mount_point)

    if not mpt:
        return f"{path} could not be mounted"

    tmp = os.path.join(mpt, "tmp")
    log.debug("Attempting to create directory %s", tmp)
    try:
        os.makedirs(tmp)
    except OSError:
        if not os.path.isdir(tmp):
            raise
    cfg_files = mkconfig(
        config,
        tmp=tmp,
        id_=id_,
        approve_key=approve_key,
        pub_key=pub_key,
        priv_key=priv_key,
    )

    if _check_install(mpt):
        # salt-minion is already installed, just move the config and keys
        # into place
        log.info("salt-minion pre-installed on image, configuring as %s", id_)
        minion_config = salt.config.minion_config(cfg_files["config"])
        pki_dir = minion_config["pki_dir"]
        if not os.path.isdir(os.path.join(mpt, pki_dir.lstrip("/"))):
            __salt__["file.makedirs"](os.path.join(mpt, pki_dir.lstrip("/"), ""))
        os.rename(
            cfg_files["privkey"], os.path.join(mpt, pki_dir.lstrip("/"), "minion.pem")
        )
        os.rename(
            cfg_files["pubkey"], os.path.join(mpt, pki_dir.lstrip("/"), "minion.pub")
        )
        os.rename(cfg_files["config"], os.path.join(mpt, "etc/salt/minion"))
        res = True
    elif install:
        log.info("Attempting to install salt-minion to %s", mpt)
        res = _install(mpt)
    elif prep_install:
        log.error(
            "The prep_install option is no longer supported. Please use "
            "the bootstrap script installed with Salt, located at %s.",
            salt.syspaths.BOOTSTRAP,
        )
        res = False
    else:
        log.warning("No useful action performed on %s", mpt)
        res = False

    _umount(mpt, path, ftype)
    return res


def mkconfig(
    config=None, tmp=None, id_=None, approve_key=True, pub_key=None, priv_key=None
):
    """
    Generate keys and config and put them in a tmp directory.

    pub_key
        absolute path or file content of an optional preseeded salt key

    priv_key
        absolute path or file content of an optional preseeded salt key

    CLI Example:

    .. code-block:: bash

        salt 'minion' seed.mkconfig [config=config_data] [tmp=tmp_dir] \\
                [id_=minion_id] [approve_key=(true|false)]
    """
    if tmp is None:
        tmp = tempfile.mkdtemp()
    if config is None:
        config = {}
    if "master" not in config and __opts__["master"] != "salt":
        config["master"] = __opts__["master"]
    if id_:
        config["id"] = id_

    # Write the new minion's config to a tmp file
    tmp_config = os.path.join(tmp, "minion")
    with salt.utils.files.fopen(tmp_config, "w+") as fp_:
        fp_.write(salt.utils.cloud.salt_config_to_yaml(config))

    # Generate keys for the minion
    pubkeyfn = os.path.join(tmp, "minion.pub")
    privkeyfn = os.path.join(tmp, "minion.pem")
    preseeded = pub_key and priv_key
    if preseeded:
        log.debug("Writing minion.pub to %s", pubkeyfn)
        log.debug("Writing minion.pem to %s", privkeyfn)
        with salt.utils.files.fopen(pubkeyfn, "w") as fic:
            fic.write(salt.utils.stringutils.to_str(_file_or_content(pub_key)))
        with salt.utils.files.fopen(privkeyfn, "w") as fic:
            fic.write(salt.utils.stringutils.to_str(_file_or_content(priv_key)))
        os.chmod(pubkeyfn, 0o600)
        os.chmod(privkeyfn, 0o600)
    else:
        salt.crypt.gen_keys(tmp, "minion", 2048)
    if approve_key and not preseeded:
        with salt.utils.files.fopen(pubkeyfn) as fp_:
            pubkey = salt.utils.stringutils.to_unicode(fp_.read())
            __salt__["pillar.ext"]({"virtkey": [id_, pubkey]})

    return {"config": tmp_config, "pubkey": pubkeyfn, "privkey": privkeyfn}


def _install(mpt):
    """
    Determine whether salt-minion is installed and, if not,
    install it.
    Return True if install is successful or already installed.
    """
    _check_resolv(mpt)
    boot_, tmppath = prep_bootstrap(mpt) or salt.syspaths.BOOTSTRAP
    # Exec the chroot command
    cmd = "if type salt-minion; then exit 0; "
    cmd += "else sh {} -c /tmp; fi".format(os.path.join(tmppath, "bootstrap-salt.sh"))
    return not __salt__["cmd.run_chroot"](mpt, cmd, python_shell=True)["retcode"]


def _check_resolv(mpt):
    """
    Check that the resolv.conf is present and populated
    """
    resolv = os.path.join(mpt, "etc/resolv.conf")
    replace = False
    if os.path.islink(resolv):
        resolv = os.path.realpath(resolv)
        if not os.path.isdir(os.path.dirname(resolv)):
            os.makedirs(os.path.dirname(resolv))
    if not os.path.isfile(resolv):
        replace = True
    if not replace:
        with salt.utils.files.fopen(resolv, "rb") as fp_:
            conts = salt.utils.stringutils.to_unicode(fp_.read())
            if "nameserver" not in conts:
                replace = True
            if "nameserver 127.0.0.1" in conts:
                replace = True
    if replace:
        shutil.copy("/etc/resolv.conf", resolv)


def _check_install(root):
    sh_ = "/bin/sh"
    if os.path.isfile(os.path.join(root, "bin/bash")):
        sh_ = "/bin/bash"

    cmd = "if ! type salt-minion; then exit 1; fi"
    cmd = f"chroot '{root}' {sh_} -c '{cmd}'"

    return not __salt__["cmd.retcode"](cmd, output_loglevel="quiet", python_shell=True)
