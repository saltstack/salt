"""
Support for htpasswd module. Requires the apache2-utils package for Debian-based distros.

.. versionadded:: 2014.7.0

.. code-block:: yaml

    username:
      webutil.user_exists:
        - password: secr3t
        - htpasswd_file: /etc/nginx/htpasswd
        - options: d
        - force: true

"""


import salt.utils.path

__virtualname__ = "webutil"


def __virtual__():
    """
    depends on webutil module
    """
    if salt.utils.path.which("htpasswd"):
        return __virtualname__
    return (False, "Command not found: htpasswd")


def user_exists(
    name,
    password=None,
    htpasswd_file=None,
    options="",
    force=False,
    runas=None,
    update=False,
):
    """
    Make sure the user is inside the specified htpasswd file

    name
        User name

    password
        User password

    htpasswd_file
        Path to the htpasswd file

    options
        See :mod:`salt.modules.htpasswd.useradd`

    force
        Touch the file even if user already created

    runas
        The system user to run htpasswd command with

    update
        Update an existing user's password if it's different from what's in
        the htpasswd file (unlike force, which updates regardless)

    """
    ret = {"name": name, "changes": {}, "comment": "", "result": None}

    if __salt__["file.file_exists"](htpasswd_file):
        exists = (
            __salt__["file.grep"](htpasswd_file, "^{}:".format(name))["retcode"] == 0
        )
    else:
        exists = False

    # If user exists, but we're supposed to update the password, find out if
    # it's changed, but not if we're forced to update the file regardless.
    password_changed = False
    if exists and update and not force:
        password_changed = not __salt__["webutil.verify"](
            htpasswd_file, name, password, opts=options, runas=runas
        )

    if not exists or password_changed or force:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "User '{}' is set to be added to htpasswd file".format(
                name
            )
            ret["changes"] = {name: True}
            return ret

        useradd_ret = __salt__["webutil.useradd"](
            htpasswd_file, name, password, opts=options, runas=runas
        )
        if useradd_ret["retcode"] == 0:
            ret["result"] = True
            ret["comment"] = useradd_ret["stderr"]
            ret["changes"] = {name: True}
            return ret
        else:
            ret["result"] = False
            ret["comment"] = useradd_ret["stderr"]
            return ret

    if __opts__["test"] and ret["changes"]:
        ret["result"] = None
    else:
        ret["result"] = True
    ret["comment"] = "User already known"
    return ret


def user_absent(name, htpasswd_file=None, runas=None):
    """
    Make sure the user is not in the specified htpasswd file

    name
        User name

    htpasswd_file
        Path to the htpasswd file

    runas
        The system user to run htpasswd command with

    """
    ret = {"name": name, "changes": {}, "comment": "", "result": None}

    exists = __salt__["file.grep"](htpasswd_file, "^{}:".format(name))["retcode"] == 0

    if not exists:
        if __opts__["test"]:
            ret["result"] = None
        else:
            ret["result"] = True
        ret["comment"] = "User already not in file"
    else:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "User '{}' is set to be removed from htpasswd file".format(
                name
            )
            ret["changes"] = {name: True}
        else:
            userdel_ret = __salt__["webutil.userdel"](
                htpasswd_file, name, runas=runas, all_results=True
            )

            ret["result"] = userdel_ret["retcode"] == 0
            ret["comment"] = userdel_ret["stderr"]

            if ret["result"]:
                ret["changes"] = {name: True}

    return ret
