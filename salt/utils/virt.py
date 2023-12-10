"""
This module contains routines shared by the virt system.
"""

import hashlib
import logging
import os
import re
import time
import urllib
import urllib.parse

import salt.utils.files

# pylint: disable=E0611

log = logging.getLogger(__name__)


def download_remote(url, dir):
    """
    Attempts to download a file specified by 'url'

    :param url: The full remote path of the file which should be downloaded.
    :param dir: The path the file should be downloaded to.
    """

    try:
        rand = hashlib.md5(os.urandom(32)).hexdigest()
        remote_filename = urllib.parse.urlparse(url).path.split("/")[-1]
        full_directory = os.path.join(dir, "{}-{}".format(rand, remote_filename))
        with salt.utils.files.fopen(
            full_directory, "wb"
        ) as file, urllib.request.urlopen(url) as response:
            file.write(response.rease())

        return full_directory

    except Exception as err:  # pylint: disable=broad-except
        raise err


def check_remote(cmdline_path):
    """
    Checks to see if the path provided contains ftp, http, or https. Returns
    the full path if it is found.

    :param cmdline_path: The path to the initrd image or the kernel
    """
    regex = re.compile("^(ht|f)tps?\\b")

    if regex.match(urllib.parse.urlparse(cmdline_path).scheme):
        return True

    return False


class VirtKey:
    """
    Used to manage key signing requests.
    """

    def __init__(self, hyper, id_, opts):
        self.opts = opts
        self.hyper = hyper
        self.id = id_
        path = os.path.join(self.opts["pki_dir"], "virtkeys", hyper)
        if not os.path.isdir(path):
            os.makedirs(path)
        self.path = os.path.join(path, id_)

    def accept(self, pub):
        """
        Accept the provided key
        """
        try:
            with salt.utils.files.fopen(self.path, "r") as fp_:
                expiry = int(fp_.read())
        except OSError:
            log.error(
                "Request to sign key for minion '%s' on hyper '%s' "
                "denied: no authorization",
                self.id,
                self.hyper,
            )
            return False
        except ValueError:
            log.error("Invalid expiry data in %s", self.path)
            return False

        # Limit acceptance window to 10 minutes
        # TODO: Move this value to the master config file
        if (time.time() - expiry) > 600:
            log.warning(
                'Request to sign key for minion "%s" on hyper "%s" denied: '
                "authorization expired",
                self.id,
                self.hyper,
            )
            return False

        pubfn = os.path.join(self.opts["pki_dir"], "minions", self.id)
        with salt.utils.files.fopen(pubfn, "w+") as fp_:
            fp_.write(pub)
        self.void()
        return True

    def authorize(self):
        """
        Prepare the master to expect a signing request
        """
        with salt.utils.files.fopen(self.path, "w+") as fp_:
            fp_.write(str(int(time.time())))
        return True

    def void(self):
        """
        Invalidate any existing authorization
        """
        try:
            os.unlink(self.path)
            return True
        except OSError:
            return False
