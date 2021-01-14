# -*- coding: utf-8 -*-
"""
Provide authentication using local files

.. versionadded:: 2018.3.0

The `file` auth module allows simple authentication via local files. Different
filetypes are supported, including:

  1. Text files, with passwords in plaintext or hashed
  2. Apache-style htpasswd files
  3. Apache-style htdigest files

.. note::

    The ``python-passlib`` library is required when using a ``^filetype`` of
    ``htpasswd`` or ``htdigest``.

The simplest example is a plaintext file with usernames and passwords:

.. code-block:: yaml

    external_auth:
      file:
        ^filename: /etc/insecure-user-list.txt
        gene:
          - .*
        dean:
          - test.*

In this example the ``/etc/insecure-user-list.txt`` file would be formatted
as so:

.. code-block:: text

    dean:goneFishing
    gene:OceanMan

``^filename`` is the only required parameter. Any parameter that begins with
a ``^`` is passed directly to the underlying file authentication function
via ``kwargs``, with the leading ``^`` being stripped.

The text file option is configurable to work with legacy formats:

.. code-block:: yaml

    external_auth:
      file:
        ^filename: /etc/legacy_users.txt
        ^filetype: text
        ^hashtype: md5
        ^username_field: 2
        ^password_field: 3
        ^field_separator: '|'
        trey:
          - .*

This would authenticate users against a file of the following format:

.. code-block:: text

    46|trey|16a0034f90b06bf3c5982ed8ac41aab4
    555|mike|b6e02a4d2cb2a6ef0669e79be6fd02e4
    2001|page|14fce21db306a43d3b680da1a527847a
    8888|jon|c4e94ba906578ccf494d71f45795c6cb

.. note::

    The :py:func:`hashutil.digest <salt.modules.hashutil.digest>` execution
    function is used for comparing hashed passwords, so any algorithm
    supported by that function will work.

There is also support for Apache-style ``htpasswd`` and ``htdigest`` files:

.. code-block:: yaml

    external_auth:
      file:
        ^filename: /var/www/html/.htusers
        ^filetype: htpasswd
        cory:
          - .*

When using ``htdigest`` the ``^realm`` must be set:

.. code-block:: yaml

    external_auth:
      file:
        ^filename: /var/www/html/.htdigest
        ^filetype: htdigest
        ^realm: MySecureRealm
        cory:
          - .*

"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os

# Import salt utils
import salt.utils.files
import salt.utils.versions

log = logging.getLogger(__name__)

__virtualname__ = "file"


def __virtual__():
    return __virtualname__


def _get_file_auth_config():
    """
    Setup defaults and check configuration variables for auth backends
    """

    config = {
        "filetype": "text",
        "hashtype": "plaintext",
        "field_separator": ":",
        "username_field": 1,
        "password_field": 2,
    }

    for opt in __opts__["external_auth"][__virtualname__]:
        if opt.startswith("^"):
            config[opt[1:]] = __opts__["external_auth"][__virtualname__][opt]

    if "filename" not in config:
        log.error(
            "salt.auth.file: An authentication file must be specified "
            "via external_auth:file:^filename"
        )
        return False

    if not os.path.exists(config["filename"]):
        log.error(
            "salt.auth.file: The configured external_auth:file:^filename (%s)"
            "does not exist on the filesystem",
            config["filename"],
        )
        return False

    config["username_field"] = int(config["username_field"])
    config["password_field"] = int(config["password_field"])

    return config


def _text(username, password, **kwargs):
    """
    The text file function can authenticate plaintext and digest methods
    that are available in the :py:func:`hashutil.digest <salt.modules.hashutil.digest>`
    function.
    """

    filename = kwargs["filename"]
    hashtype = kwargs["hashtype"]
    field_separator = kwargs["field_separator"]
    username_field = kwargs["username_field"] - 1
    password_field = kwargs["password_field"] - 1

    with salt.utils.files.fopen(filename, "r") as pwfile:
        for line in pwfile.readlines():
            fields = line.strip().split(field_separator)

            try:
                this_username = fields[username_field]
            except IndexError:
                log.error(
                    "salt.auth.file: username field (%s) does not exist " "in file %s",
                    username_field,
                    filename,
                )
                return False
            try:
                this_password = fields[password_field]
            except IndexError:
                log.error(
                    "salt.auth.file: password field (%s) does not exist " "in file %s",
                    password_field,
                    filename,
                )
                return False

            if this_username == username:
                if hashtype == "plaintext":
                    if this_password == password:
                        return True
                else:
                    # Exceptions for unknown hash types will be raised by hashutil.digest
                    if this_password == __salt__["hashutil.digest"](password, hashtype):
                        return True

                # Short circuit if we've already found the user but the password was wrong
                return False
    return False


def _htpasswd(username, password, **kwargs):
    """
    Provide authentication via Apache-style htpasswd files
    """

    from passlib.apache import HtpasswdFile

    pwfile = HtpasswdFile(kwargs["filename"])

    # passlib below version 1.6 uses 'verify' function instead of 'check_password'
    if salt.utils.versions.version_cmp(kwargs["passlib_version"], "1.6") < 0:
        return pwfile.verify(username, password)
    else:
        return pwfile.check_password(username, password)


def _htdigest(username, password, **kwargs):
    """
    Provide authentication via Apache-style htdigest files
    """

    realm = kwargs.get("realm", None)
    if not realm:
        log.error(
            "salt.auth.file: A ^realm must be defined in "
            "external_auth:file for htdigest filetype"
        )
        return False

    from passlib.apache import HtdigestFile

    pwfile = HtdigestFile(kwargs["filename"])

    # passlib below version 1.6 uses 'verify' function instead of 'check_password'
    if salt.utils.versions.version_cmp(kwargs["passlib_version"], "1.6") < 0:
        return pwfile.verify(username, realm, password)
    else:
        return pwfile.check_password(username, realm, password)


def _htfile(username, password, **kwargs):
    """
    Gate function for _htpasswd and _htdigest authentication backends
    """

    filetype = kwargs.get("filetype", "htpasswd").lower()

    try:
        import passlib

        kwargs["passlib_version"] = passlib.__version__
    except ImportError:
        log.error(
            "salt.auth.file: The python-passlib library is required " "for %s filetype",
            filetype,
        )
        return False

    if filetype == "htdigest":
        return _htdigest(username, password, **kwargs)
    else:
        return _htpasswd(username, password, **kwargs)


FILETYPE_FUNCTION_MAP = {"text": _text, "htpasswd": _htfile, "htdigest": _htfile}


def auth(username, password):
    """
    File based authentication

    ^filename
        The path to the file to use for authentication.

    ^filetype
        The type of file: ``text``, ``htpasswd``, ``htdigest``.

        Default: ``text``

    ^realm
        The realm required by htdigest authentication.

    .. note::
        The following parameters are only used with the ``text`` filetype.

    ^hashtype
        The digest format of the password. Can be ``plaintext`` or any digest
        available via :py:func:`hashutil.digest <salt.modules.hashutil.digest>`.

        Default: ``plaintext``

    ^field_separator
        The character to use as a delimiter between fields in a text file.

        Default: ``:``

    ^username_field
        The numbered field in the text file that contains the username, with
        numbering beginning at 1 (one).

        Default: ``1``

    ^password_field
        The numbered field in the text file that contains the password, with
        numbering beginning at 1 (one).

        Default: ``2``
    """

    config = _get_file_auth_config()

    if not config:
        return False

    auth_function = FILETYPE_FUNCTION_MAP.get(config["filetype"], "text")

    return auth_function(username, password, **config)
