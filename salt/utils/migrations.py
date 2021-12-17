"""
Migration tools
"""

import os.path
import shutil

import salt.syspaths as syspaths


def migrate_paths(opts):
    """
    Migrate old minion and master pki file paths to new ones.
    """
    oldpki_dir = os.path.join(syspaths.CONFIG_DIR, "pki")

    if not os.path.exists(oldpki_dir):
        # There's not even a pki directory, don't bother migrating
        return

    newpki_dir = opts["pki_dir"]

    if opts["default_include"].startswith("master"):
        keepers = [
            "master.pem",
            "master.pub",
            "syndic_master.pub",
            "minions",
            "minions_pre",
            "minions_rejected",
        ]
        if not os.path.exists(newpki_dir):
            os.makedirs(newpki_dir)
        for item in keepers:
            oi_path = os.path.join(oldpki_dir, item)
            ni_path = os.path.join(newpki_dir, item)
            if os.path.exists(oi_path) and not os.path.exists(ni_path):
                shutil.move(oi_path, ni_path)

    if opts["default_include"].startswith("minion"):
        keepers = [
            "minion_master.pub",
            "minion.pem",
            "minion.pub",
        ]
        if not os.path.exists(newpki_dir):
            os.makedirs(newpki_dir)
        for item in keepers:
            oi_path = os.path.join(oldpki_dir, item)
            ni_path = os.path.join(newpki_dir, item)
            if os.path.exists(oi_path) and not os.path.exists(ni_path):
                shutil.move(oi_path, ni_path)
