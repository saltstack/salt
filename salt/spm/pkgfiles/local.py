# -*- coding: utf-8 -*-
"""
This module allows SPM to use the local filesystem to install files for SPM.

.. versionadded:: 2015.8.0
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import os.path

# Import Salt libs
import salt.syspaths
import salt.utils.files
import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext import six

# Get logging started
log = logging.getLogger(__name__)
FILE_TYPES = ("c", "d", "g", "l", "r", "s", "m")
# c: config file
# d: documentation file
# g: ghost file (i.e. the file contents are not included in the package payload)
# l: license file
# r: readme file
# s: SLS file
# m: Salt module


def init(**kwargs):
    """
    Initialize the directories for the files
    """
    formula_path = __opts__["formula_path"]
    pillar_path = __opts__["pillar_path"]
    reactor_path = __opts__["reactor_path"]
    for dir_ in (formula_path, pillar_path, reactor_path):
        if not os.path.exists(dir_):
            os.makedirs(dir_)
    return {
        "formula_path": formula_path,
        "pillar_path": pillar_path,
        "reactor_path": reactor_path,
    }


def check_existing(package, pkg_files, formula_def, conn=None):
    """
    Check the filesystem for existing files
    """
    if conn is None:
        conn = init()

    node_type = six.text_type(__opts__.get("spm_node_type"))

    existing_files = []
    for member in pkg_files:
        if member.isdir():
            continue

        tld = formula_def.get("top_level_dir", package)
        new_name = member.name.replace("{0}/".format(package), "")
        if not new_name.startswith(tld):
            continue

        if member.name.startswith("{0}/_".format(package)):
            if node_type in ("master", "minion"):
                # Module files are distributed via extmods directory
                out_file = os.path.join(
                    salt.syspaths.CACHE_DIR,
                    node_type,
                    "extmods",
                    new_name.replace("_", ""),
                )
            else:
                # Module files are distributed via _modules, _states, etc
                out_file = os.path.join(conn["formula_path"], new_name)
        elif member.name == "{0}/pillar.example".format(package):
            # Pillars are automatically put in the pillar_path
            new_name = "{0}.sls.orig".format(package)
            out_file = os.path.join(conn["pillar_path"], new_name)
        elif package.endswith("-conf"):
            # Configuration files go into /etc/salt/
            out_file = os.path.join(salt.syspaths.CONFIG_DIR, new_name)
        elif package.endswith("-reactor"):
            # Reactor files go into /srv/reactor/
            out_file = os.path.join(conn["reactor_path"], member.name)
        else:
            out_file = os.path.join(conn["formula_path"], member.name)

        if os.path.exists(out_file):
            existing_files.append(out_file)
            if not __opts__["force"]:
                log.error("%s already exists, not installing", out_file)

    return existing_files


def install_file(package, formula_tar, member, formula_def, conn=None):
    """
    Install a single file to the file system
    """
    if member.name == package:
        return False

    if conn is None:
        conn = init()

    node_type = six.text_type(__opts__.get("spm_node_type"))

    out_path = conn["formula_path"]

    tld = formula_def.get("top_level_dir", package)
    new_name = member.name.replace("{0}/".format(package), "", 1)
    if (
        not new_name.startswith(tld)
        and not new_name.startswith("_")
        and not new_name.startswith("pillar.example")
        and not new_name.startswith("README")
    ):
        log.debug("%s not in top level directory, not installing", new_name)
        return False

    for line in formula_def.get("files", []):
        tag = ""
        for ftype in FILE_TYPES:
            if line.startswith("{0}|".format(ftype)):
                tag = line.split("|", 1)[0]
                line = line.split("|", 1)[1]
        if tag and new_name == line:
            if tag in ("c", "d", "g", "l", "r"):
                out_path = __opts__["spm_share_dir"]
            elif tag in ("s", "m"):
                pass

    if member.name.startswith("{0}/_".format(package)):
        if node_type in ("master", "minion"):
            # Module files are distributed via extmods directory
            member.name = new_name.name.replace("{0}/_".format(package), "")
            out_path = os.path.join(salt.syspaths.CACHE_DIR, node_type, "extmods",)
        else:
            # Module files are distributed via _modules, _states, etc
            member.name = new_name.name.replace("{0}/".format(package), "")
    elif member.name == "{0}/pillar.example".format(package):
        # Pillars are automatically put in the pillar_path
        member.name = "{0}.sls.orig".format(package)
        out_path = conn["pillar_path"]
    elif package.endswith("-conf"):
        # Configuration files go into /etc/salt/
        member.name = member.name.replace("{0}/".format(package), "")
        out_path = salt.syspaths.CONFIG_DIR
    elif package.endswith("-reactor"):
        # Reactor files go into /srv/reactor/
        out_path = __opts__["reactor_path"]

    # This ensures that double directories (i.e., apache/apache/) don't
    # get created
    comps = member.path.split("/")
    if len(comps) > 1 and comps[0] == comps[1]:
        member.path = "/".join(comps[1:])

    log.debug("Installing package file %s to %s", member.name, out_path)
    formula_tar.extract(member, out_path)

    return out_path


def remove_file(path, conn=None):
    """
    Remove a single file from the file system
    """
    if conn is None:
        conn = init()

    log.debug("Removing package file %s", path)
    os.remove(path)


def hash_file(path, hashobj, conn=None):
    """
    Get the hexdigest hash value of a file
    """
    if os.path.isdir(path):
        return ""

    with salt.utils.files.fopen(path, "r") as f:
        hashobj.update(salt.utils.stringutils.to_bytes(f.read()))
        return hashobj.hexdigest()


def path_exists(path):
    """
    Check to see whether the file already exists
    """
    return os.path.exists(path)


def path_isdir(path):
    """
    Check to see whether the file already exists
    """
    return os.path.isdir(path)
