"""
These commands are used to build Salt packages.
"""
# pylint: disable=resource-leakage,broad-except
from __future__ import annotations

import fnmatch
import logging
import os
import pathlib
import shutil
import sys

from ptscripts import Context, command_group

log = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Define the command group
pkg = command_group(name="pkg", help="Packaging Related Commands", description=__doc__)


@pkg.command(
    name="set-salt-version",
    arguments={
        "salt_version": {
            "help": (
                "The salt version to write to 'salt/_version.txt'. If not passed "
                "it will be discovered by running 'python3 salt/version.py'."
            ),
            "nargs": "?",
            "default": None,
        },
        "overwrite": {
            "help": "Overwrite 'salt/_version.txt' if it already exists",
        },
    },
)
def set_salt_version(ctx: Context, salt_version: str, overwrite: bool = False):
    """
    Write the Salt version to 'salt/_version.txt'
    """
    salt_version_file = REPO_ROOT / "salt" / "_version.txt"
    if salt_version_file.exists():
        if not overwrite:
            ctx.error("The 'salt/_version.txt' file already exists")
            ctx.exit(1)
        salt_version_file.unlink()
    if salt_version is None:
        if not REPO_ROOT.joinpath(".git").exists():
            ctx.error(
                "Apparently not running from a Salt repository checkout. "
                "Unable to discover the Salt version."
            )
            ctx.exit(1)
            ctx.info("Discovering the Salt version...")
        ret = ctx.run(shutil.which("python3"), "salt/version.py", capture=True)
        salt_version = ret.stdout.strip().decode()
        ctx.info(f"Discovered Salt version: {salt_version!r}")

    if not REPO_ROOT.joinpath("salt").is_dir():
        ctx.error(
            "The path 'salt/' is not a directory. Unable to write 'salt/_version.txt'"
        )
        ctx.exit(1)

    try:
        REPO_ROOT.joinpath("salt/_version.txt").write_text(salt_version)
    except Exception as exc:
        ctx.error(f"Unable to write 'salt/_version.txt': {exc}")
        ctx.exit(1)

    ctx.info(f"Successfuly wrote {salt_version!r} to 'salt/_version.txt'")

    gh_env_file = os.environ.get("GITHUB_ENV", None)
    if gh_env_file is not None:
        variable_text = f"SALT_VERSION={salt_version}"
        ctx.info(f"Writing '{variable_text}' to '$GITHUB_ENV' file:", gh_env_file)
        with open(gh_env_file, "w", encoding="utf-8") as wfh:
            wfh.write(f"{variable_text}\n")

    gh_output_file = os.environ.get("GITHUB_OUTPUT", None)
    if gh_output_file is not None:
        variable_text = f"salt-version={salt_version}"
        ctx.info(f"Writing '{variable_text}' to '$GITHUB_OUTPUT' file:", gh_output_file)
        with open(gh_output_file, "w", encoding="utf-8") as wfh:
            wfh.write(f"{variable_text}\n")

    ctx.exit(0)


@pkg.command(
    name="pre-archive-cleanup",
    arguments={
        "path": {
            "help": (
                "The salt version to write to 'salt/_version.txt'. If not passed "
                "it will be discovered by running 'python3 salt/version.py'."
            ),
            "metavar": "PATH_TO_CLEANUP",
        },
    },
)
def pre_archive_cleanup(ctx: Context, path: str):
    """
    Clean the provided path of paths that shouyld not be included in the archive.

    For example:

        * `__pycache__` directories
        * `*.pyc` files
        * `*.pyo` files

    When running on Windows and macOS, some additional cleanup is also done.
    """
    dir_patterns = [
        "**/__pycache__",
        # "**/tests",
        "**/site-packages/cheroot/test",
        "**/site-packages/cherrypy/test",
        "**/site-packages/gitdb/test",
        "**/site-packages/psutil/tests",
        "**/site-packages/smmap/test",
        "**/site-packages/zmq/tests",
    ]
    file_patterns = [
        "*.pyc",
        "*.pyo",
        # "test_*.py",
    ]
    if sys.platform.lower().startswith("win"):
        dir_patterns.extend(
            [
                "**/artifacts/salt/configs",
                "**/site-packages/adodbapi",
                "**/site-packages/isapi",
                "**/site-packages/pythonwin",
                "**/site-packages/win32/demos",
                "**/site-packages/tempora/tests",
                "**/site-packages/win32/test",
                "**/site-packages/win32com/test",
            ]
        )
        file_patterns.extend(
            [
                "**/*.chm" "**/Scripts/py.exe",
                "**/Scripts/pyw.exe",
                "**/Scripts/pythonw.exe",
                "**/Scripts/venvlauncher.exe",
                "**/Scripts/venvwlauncher.exe",
                # Non Windows execution modules
                "**/site-packages/salt/modules/aacme.py*",
                "**/site-packages/salt/modules/aix.py*",
                "**/site-packages/salt/modules/alternatives.py*",
                "**/site-packages/salt/modules/apcups.py*",
                "**/site-packages/salt/modules/apf.py*",
                "**/site-packages/salt/modules/apt.py*",
                "**/site-packages/salt/modules/arista.py*",
                "**/site-packages/salt/modules/at.py*",
                "**/site-packages/salt/modules/bcache.py*",
                "**/site-packages/salt/modules/blockdev.py*",
                "**/site-packages/salt/modules/bluez.py*",
                "**/site-packages/salt/modules/bridge.py*",
                "**/site-packages/salt/modules/bsd.py*",
                "**/site-packages/salt/modules/btrfs.py*",
                "**/site-packages/salt/modules/ceph.py*",
                "**/site-packages/salt/modules/container_resource.py*",
                "**/site-packages/salt/modules/cron.py*",
                "**/site-packages/salt/modules/csf.py*",
                "**/site-packages/salt/modules/daemontools.py*",
                "**/site-packages/salt/modules/deb*.py*",
                "**/site-packages/salt/modules/devmap.py*",
                "**/site-packages/salt/modules/dpkg.py*",
                "**/site-packages/salt/modules/ebuild.py*",
                "**/site-packages/salt/modules/eix.py*",
                "**/site-packages/salt/modules/eselect.py*",
                "**/site-packages/salt/modules/ethtool.py*",
                "**/site-packages/salt/modules/extfs.py*",
                "**/site-packages/salt/modules/firewalld.py*",
                "**/site-packages/salt/modules/freebsd.py*",
                "**/site-packages/salt/modules/genesis.py*",
                "**/site-packages/salt/modules/gentoo.py*",
                "**/site-packages/salt/modules/glusterfs.py*",
                "**/site-packages/salt/modules/gnomedesktop.py*",
                "**/site-packages/salt/modules/groupadd.py*",
                "**/site-packages/salt/modules/grub_legacy.py*",
                "**/site-packages/salt/modules/guestfs.py*",
                "**/site-packages/salt/modules/htpasswd.py*",
                "**/site-packages/salt/modules/ilo.py*",
                "**/site-packages/salt/modules/img.py*",
                "**/site-packages/salt/modules/incron.py*",
                "**/site-packages/salt/modules/inspector.py*",
                "**/site-packages/salt/modules/ipset.py*",
                "**/site-packages/salt/modules/iptables.py*",
                "**/site-packages/salt/modules/iwtools.py*",
                "**/site-packages/salt/modules/k8s.py*",
                "**/site-packages/salt/modules/kapacitor.py*",
                "**/site-packages/salt/modules/keyboard.py*",
                "**/site-packages/salt/modules/keystone.py*",
                "**/site-packages/salt/modules/kmod.py*",
                "**/site-packages/salt/modules/layman.py*",
                "**/site-packages/salt/modules/linux.py*",
                "**/site-packages/salt/modules/localemod.py*",
                "**/site-packages/salt/modules/locate.py*",
                "**/site-packages/salt/modules/logadm.py*",
                "**/site-packages/salt/modules/logrotate.py*",
                "**/site-packages/salt/modules/lvs.py*",
                "**/site-packages/salt/modules/lxc.py*",
                "**/site-packages/salt/modules/mac.py*",
                "**/site-packages/salt/modules/makeconf.py*",
                "**/site-packages/salt/modules/mdadm.py*",
                "**/site-packages/salt/modules/mdata.py*",
                "**/site-packages/salt/modules/monit.py*",
                "**/site-packages/salt/modules/moosefs.py*",
                "**/site-packages/salt/modules/mount.py*",
                "**/site-packages/salt/modules/napalm.py*",
                "**/site-packages/salt/modules/netbsd.py*",
                "**/site-packages/salt/modules/netscaler.py*",
                "**/site-packages/salt/modules/neutron.py*",
                "**/site-packages/salt/modules/nfs3.py*",
                "**/site-packages/salt/modules/nftables.py*",
                "**/site-packages/salt/modules/nova.py*",
                "**/site-packages/salt/modules/nspawn.py*",
                "**/site-packages/salt/modules/openbsd.py*",
                "**/site-packages/salt/modules/openstack.py*",
                "**/site-packages/salt/modules/openvswitch.py*",
                "**/site-packages/salt/modules/opkg.py*",
                "**/site-packages/salt/modules/pacman.py*",
                "**/site-packages/salt/modules/parallels.py*",
                "**/site-packages/salt/modules/parted.py*",
                "**/site-packages/salt/modules/pcs.py*",
                "**/site-packages/salt/modules/pkgin.py*",
                "**/site-packages/salt/modules/pkgng.py*",
                "**/site-packages/salt/modules/pkgutil.py*",
                "**/site-packages/salt/modules/portage_config.py*",
                "**/site-packages/salt/modules/postfix.py*",
                "**/site-packages/salt/modules/poudriere.py*",
                "**/site-packages/salt/modules/powerpath.py*",
                "**/site-packages/salt/modules/pw_.py*",
                "**/site-packages/salt/modules/qemu_.py*",
                "**/site-packages/salt/modules/quota.py*",
                "**/site-packages/salt/modules/redismod.py*",
                "**/site-packages/salt/modules/restartcheck.py*",
                "**/site-packages/salt/modules/rh_.py*",
                "**/site-packages/salt/modules/riak.py*",
                "**/site-packages/salt/modules/rpm.py*",
                "**/site-packages/salt/modules/runit.py*",
                "**/site-packages/salt/modules/s6.py*",
                "**/site-packages/salt/modules/scsi.py*",
                "**/site-packages/salt/modules/seed.py*",
                "**/site-packages/salt/modules/sensors.py*",
                "**/site-packages/salt/modules/service.py*",
                "**/site-packages/salt/modules/shadow.py*",
                "**/site-packages/salt/modules/smartos.py*",
                "**/site-packages/salt/modules/smf.py*",
                "**/site-packages/salt/modules/snapper.py*",
                "**/site-packages/salt/modules/solaris.py*",
                "**/site-packages/salt/modules/solr.py*",
                "**/site-packages/salt/modules/ssh_.py*",
                "**/site-packages/salt/modules/supervisord.py*",
                "**/site-packages/salt/modules/sysbench.py*",
                "**/site-packages/salt/modules/sysfs.py*",
                "**/site-packages/salt/modules/sysrc.py*",
                "**/site-packages/salt/modules/system.py*",
                "**/site-packages/salt/modules/test_virtual.py*",
                "**/site-packages/salt/modules/timezone.py*",
                "**/site-packages/salt/modules/trafficserver.py*",
                "**/site-packages/salt/modules/tuned.py*",
                "**/site-packages/salt/modules/udev.py*",
                "**/site-packages/salt/modules/upstart.py*",
                "**/site-packages/salt/modules/useradd.py*",
                "**/site-packages/salt/modules/uswgi.py*",
                "**/site-packages/salt/modules/varnish.py*",
                "**/site-packages/salt/modules/vbox.py*",
                "**/site-packages/salt/modules/virt.py*",
                "**/site-packages/salt/modules/xapi.py*",
                "**/site-packages/salt/modules/xbpspkg.py*",
                "**/site-packages/salt/modules/xfs.py*",
                "**/site-packages/salt/modules/yum*.py*",
                "**/site-packages/salt/modules/zfs.py*",
                "**/site-packages/salt/modules/znc.py*",
                "**/site-packages/salt/modules/zpool.py*",
                "**/site-packages/salt/modules/zypper.py*",
                # Non Windows state modules
                "**/site-packages/salt/states/acme.py*",
                "**/site-packages/salt/states/alternatives.py*",
                "**/site-packages/salt/states/apt.py*",
                "**/site-packages/salt/states/at.py*",
                "**/site-packages/salt/states/blockdev.py*",
                "**/site-packages/salt/states/ceph.py*",
                "**/site-packages/salt/states/cron.py*",
                "**/site-packages/salt/states/csf.py*",
                "**/site-packages/salt/states/deb.py*",
                "**/site-packages/salt/states/eselect.py*",
                "**/site-packages/salt/states/ethtool.py*",
                "**/site-packages/salt/states/firewalld.py*",
                "**/site-packages/salt/states/glusterfs.py*",
                "**/site-packages/salt/states/gnome.py*",
                "**/site-packages/salt/states/htpasswd.py*",
                "**/site-packages/salt/states/incron.py*",
                "**/site-packages/salt/states/ipset.py*",
                "**/site-packages/salt/states/iptables.py*",
                "**/site-packages/salt/states/k8s.py*",
                "**/site-packages/salt/states/kapacitor.py*",
                "**/site-packages/salt/states/keyboard.py*",
                "**/site-packages/salt/states/keystone.py*",
                "**/site-packages/salt/states/kmod.py*",
                "**/site-packages/salt/states/layman.py*",
                "**/site-packages/salt/states/linux.py*",
                "**/site-packages/salt/states/lxc.py*",
                "**/site-packages/salt/states/mac.py*",
                "**/site-packages/salt/states/makeconf.py*",
                "**/site-packages/salt/states/mdadm.py*",
                "**/site-packages/salt/states/monit.py*",
                "**/site-packages/salt/states/mount.py*",
                "**/site-packages/salt/states/nftables.py*",
                "**/site-packages/salt/states/pcs.py*",
                "**/site-packages/salt/states/pkgng.py*",
                "**/site-packages/salt/states/portage.py*",
                "**/site-packages/salt/states/powerpath.py*",
                "**/site-packages/salt/states/quota.py*",
                "**/site-packages/salt/states/redismod.py*",
                "**/site-packages/salt/states/smartos.py*",
                "**/site-packages/salt/states/snapper.py*",
                "**/site-packages/salt/states/ssh.py*",
                "**/site-packages/salt/states/supervisord.py*",
                "**/site-packages/salt/states/sysrc.py*",
                "**/site-packages/salt/states/trafficserver.py*",
                "**/site-packages/salt/states/tuned.py*",
                "**/site-packages/salt/states/vbox.py*",
                "**/site-packages/salt/states/virt.py.py*",
                "**/site-packages/salt/states/zfs.py*",
                "**/site-packages/salt/states/zpool.py*",
            ]
        )
    if sys.platform.lower().startswith("darwin"):
        dir_patterns.extend(
            [
                "**/pkgconfig",
                "**/share",
                "**/artifacts/salt/opt",
                "**/artifacts/salt/etc",
                "**/artifacts/salt/Lib",
            ]
        )
    for root, dirs, files in os.walk(path, topdown=True, followlinks=False):
        for dirname in dirs:
            path = os.path.join(root, dirname)
            if not os.path.exists(path):
                continue
            match_path = pathlib.Path(path).as_posix()
            for pattern in dir_patterns:
                if fnmatch.fnmatch(str(match_path), pattern):
                    ctx.info(f"Deleting directory: {match_path}")
                    shutil.rmtree(path)
        for filename in files:
            path = os.path.join(root, filename)
            if not os.path.exists(path):
                continue
            match_path = pathlib.Path(path).as_posix()
            for pattern in file_patterns:
                if fnmatch.fnmatch(str(match_path), pattern):
                    ctx.info(f"Deleting file: {match_path}")
                    try:
                        os.remove(path)
                    except FileNotFoundError:
                        pass
