# -*- coding: utf-8 -*-
"""
    :copyright: Copyright 2013-2017 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    tests.support.win_installer
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Fetches the binary Windows installer
"""
from __future__ import absolute_import

import hashlib
import re

import requests

PREFIX = "Salt-Minion-"
REPO = "https://repo.saltstack.com/windows"


def iter_installers(content):
    """
    Parse a list of windows installer links and their corresponding md5
    checksum links.
    """
    HREF_RE = '<a href="(.*?)">'
    installer, md5 = None, None
    for m in re.finditer(HREF_RE, content):
        x = m.groups()[0]
        if not x.startswith(PREFIX):
            continue
        if x.endswith(("zip", "sha256")):
            continue
        if installer:
            if x != installer + ".md5":
                raise Exception("Unable to parse response")
            md5 = x
            yield installer, md5
            installer, md5 = None, None
        else:
            installer = x


def split_installer(name):
    """
    Return a tuple of the salt version, python verison and architecture from an
    installer name.
    """
    x = name[len(PREFIX) :]
    return x.split("-")[:3]


def latest_version(repo=REPO):
    """
    Return the latest version found on the salt repository webpage.
    """
    content = requests.get(repo).content.decode("utf-8")
    for name, md5 in iter_installers(content):
        pass
    return split_installer(name)[0]


def installer_name(salt_ver, py_ver="Py2", arch="AMD64"):
    """
    Create an installer file name
    """
    return "Salt-Minion-{}-{}-{}-Setup.exe".format(salt_ver, py_ver, arch)


def latest_installer_name(repo=REPO, **kwargs):
    """
    Fetch the latest installer name
    """
    return installer_name(latest_version(repo), **kwargs)


def download_and_verify(fp, name, repo=REPO):
    """
    Download an installer and verify it's contents.
    """
    md5 = "{}.md5".format(name)
    url = lambda x: "{}/{}".format(repo, x)
    resp = requests.get(url(md5))
    if resp.status_code != 200:
        raise Exception("Unable to fetch installer md5")
    installer_md5 = resp.text.strip().split()[0].lower()
    resp = requests.get(url(name), stream=True)
    if resp.status_code != 200:
        raise Exception("Unable to fetch installer")
    md5hsh = hashlib.md5()
    for chunk in resp.iter_content(chunk_size=1024):
        md5hsh.update(chunk)
        fp.write(chunk)
    if md5hsh.hexdigest() != installer_md5:
        raise Exception(
            "Installer's hash does not match {} != {}".format(
                md5hsh.hexdigest(), installer_md5
            )
        )
