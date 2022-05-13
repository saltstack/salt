"""
    :copyright: Copyright 2013-2017 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    tests.support.win_installer
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Fetches the binary Windows installer
"""

import hashlib

import requests

PREFIX = "Salt-Minion-"
REPO = "https://repo.saltproject.io/windows"


def latest_installer_name(arch="AMD64", **kwargs):
    """
    Create an installer file name
    """
    return "Salt-Minion-Latest-Py3-{}-Setup.exe".format(arch)


def download_and_verify(fp, name, repo=REPO):
    """
    Download an installer and verify its contents.
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
