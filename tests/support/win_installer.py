"""
    :copyright: Copyright 2013-2017 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    tests.support.win_installer
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Fetches the binary Windows installer
"""

import hashlib
from html.parser import HTMLParser

import requests

PREFIX = "Salt-Minion-"
REPO = "https://packages.broadcom.com/artifactory/saltproject-generic/windows/"


def latest_installer_name(arch="AMD64", **kwargs):
    """
    Create an installer file name
    """

    # This is where windows packages are found
    # Each version is in its own directory, so we need to list the directories
    # and use the last one as the latest
    html_response = requests.get(REPO, timeout=60)

    versions = []

    # Create a class so we can define how to handle the starttag
    # We're looking for a "href" in the "a" tag which is the version
    class MyHTMLParser(HTMLParser):

        def handle_starttag(self, tag, attrs):
            # Only parse the 'anchor' tag.
            if tag == "a":
                # Check the list of defined attributes.
                for name, value in attrs:
                    # If href is defined, add the value to the list of versions
                    if name == "href":
                        versions.append(value.strip("/"))

    parser = MyHTMLParser()
    parser.feed(html_response.text)
    parser.close()

    latest = versions[-1]

    return f"{PREFIX}{latest}-Py3-{arch}-Setup.exe"


def download_and_verify(fp, name, repo=REPO):
    """
    Download an installer and verify its contents.
    """
    md5 = f"{name}.md5"

    def url(x):
        return f"{repo}/{x}"

    resp = requests.get(url(md5), timeout=60)
    if resp.status_code != 200:
        raise Exception("Unable to fetch installer md5")
    installer_md5 = resp.text.strip().split()[0].lower()
    resp = requests.get(url(name), stream=True, timeout=60)
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
