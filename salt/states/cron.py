"""
Management of cron, the Unix command scheduler
==============================================

Cron declarations require a number of parameters. The following are the
parameters used by Salt to define the various timing values for a cron job:

* ``minute``
* ``hour``
* ``daymonth``
* ``month``
* ``dayweek`` (0 to 6 are Sunday through Saturday, 7 can also be used for
  Sunday)

.. warning::

    Any timing arguments not specified take a value of ``*``. This means that
    setting ``hour`` to ``5``, while not defining the ``minute`` param, will
    result in Salt adding a job that will execute every minute between 5 and 6
    A.M.!

    Additionally, the default user for these states is ``root``. Therefore, if
    the cron job is for another user, it is necessary to specify that user with
    the ``user`` parameter.

A long time ago (before 2014.2), when making changes to an existing cron job,
the name declaration is the parameter used to uniquely identify the job,
so if an existing cron that looks like this:

.. code-block:: yaml

    date > /tmp/crontest:
      cron.present:
        - user: root
        - minute: 5

Is changed to this:

.. code-block:: yaml

    date > /tmp/crontest:
      cron.present:
        - user: root
        - minute: 7
        - hour: 2

Then the existing cron will be updated, but if the cron command is changed,
then a new cron job will be added to the user's crontab.

The current behavior is still relying on that mechanism, but you can also
specify an identifier to identify your crontabs:

.. code-block:: yaml

    date > /tmp/crontest:
      cron.present:
        - identifier: SUPERCRON
        - user: root
        - minute: 7
        - hour: 2

.. versionadded:: 2014.1.2

And, some months later, you modify it:

.. code-block:: yaml

    superscript > /tmp/crontest:
      cron.present:
        - identifier: SUPERCRON
        - user: root
        - minute: 3
        - hour: 4

.. versionadded:: 2014.1.2

The old **date > /tmp/crontest** will be replaced by
**superscript > /tmp/crontest**.

Additionally, Salt also supports running a cron every ``x minutes`` very similarly to the Unix
convention of using ``*/5`` to have a job run every five minutes. In Salt, this
looks like:

.. code-block:: yaml

    date > /tmp/crontest:
      cron.present:
        - user: root
        - minute: '*/5'

The job will now run every 5 minutes.

Additionally, the temporal parameters (minute, hour, etc.) can be randomized by
using ``random`` instead of using a specific value. For example, by using the
``random`` keyword in the ``minute`` parameter of a cron state, the same cron
job can be pushed to hundreds or thousands of hosts, and they would each use a
randomly-generated minute. This can be helpful when the cron job accesses a
network resource, and it is not desirable for all hosts to run the job
concurrently.

.. code-block:: yaml

    /path/to/cron/script:
      cron.present:
        - user: root
        - minute: random
        - hour: 2

.. versionadded:: 0.16.0

Since Salt assumes a value of ``*`` for unspecified temporal parameters, adding
a parameter to the state and setting it to ``random`` will change that value
from ``*`` to a randomized numeric value. However, if that field in the cron
entry on the minion already contains a numeric value, then using the ``random``
keyword will not modify it.

Added the opportunity to set a job with a special keyword like '@reboot' or
'@hourly'. Quotes must be used, otherwise PyYAML will strip the '@' sign.

.. code-block:: yaml

    /path/to/cron/script:
      cron.present:
        - user: root
        - special: '@hourly'

The script will be executed every reboot if cron daemon support this option.

.. code-block:: yaml

    /path/to/cron/otherscript:
      cron.absent:
        - user: root
        - special: '@daily'

This counter part definition will ensure than a job with a special keyword
is not set.
"""

import os

import salt.utils.files
from salt.modules.cron import _cron_matched, _needs_change


def __virtual__():
    if "cron.list_tab" in __salt__:
        return True
    return (False, "cron module could not be loaded")


def _check_cron(
    user,
    cmd,
    minute=None,
    hour=None,
    daymonth=None,
    month=None,
    dayweek=None,
    comment=None,
    commented=None,
    identifier=None,
    special=None,
):
    """
    Return the changes
    """
    if minute is not None:
        minute = str(minute).lower()
    if hour is not None:
        hour = str(hour).lower()
    if daymonth is not None:
        daymonth = str(daymonth).lower()
    if month is not None:
        month = str(month).lower()
    if dayweek is not None:
        dayweek = str(dayweek).lower()
    if identifier is not None:
        identifier = str(identifier)
    if commented is not None:
        commented = commented is True
    if cmd is not None:
        cmd = str(cmd)
    lst = __salt__["cron.list_tab"](user)
    if special is None:
        for cron in lst["crons"]:
            if _cron_matched(cron, cmd, identifier):
                if any(
                    [
                        _needs_change(x, y)
                        for x, y in (
                            (cron["minute"], minute),
                            (cron["hour"], hour),
                            (cron["daymonth"], daymonth),
                            (cron["month"], month),
                            (cron["dayweek"], dayweek),
                            (cron["identifier"], identifier),
                            (cron["cmd"], cmd),
                            (cron["comment"], comment),
                            (cron["commented"], commented),
                        )
                    ]
                ):
                    return "update"
                return "present"
    else:
        for cron in lst["special"]:
            if _cron_matched(cron, cmd, identifier):
                if any(
                    [
                        _needs_change(x, y)
                        for x, y in (
                            (cron["spec"], special),
                            (cron["identifier"], identifier),
                            (cron["cmd"], cmd),
                            (cron["comment"], comment),
                            (cron["commented"], commented),
                        )
                    ]
                ):
                    return "update"
                return "present"
    return "absent"


def _check_cron_env(user, name, value=None):
    """
    Return the environment changes
    """
    if value is None:
        value = ""  # Matching value set in salt.modules.cron._render_tab
    lst = __salt__["cron.list_tab"](user)
    for env in lst["env"]:
        if name == env["name"]:
            if value != env["value"]:
                return "update"
            return "present"
    return "absent"


def _get_cron_info():
    """
    Returns the proper group owner and path to the cron directory
    """
    owner = "root"
    if __grains__["os"] == "FreeBSD":
        group = "wheel"
        crontab_dir = "/var/cron/tabs"
    elif __grains__["os"] == "OpenBSD":
        group = "crontab"
        crontab_dir = "/var/cron/tabs"
    elif __grains__["os_family"] == "Solaris":
        group = "root"
        crontab_dir = "/var/spool/cron/crontabs"
    elif __grains__["os"] == "MacOS":
        group = "wheel"
        crontab_dir = "/usr/lib/cron/tabs"
    else:
        group = "root"
        crontab_dir = "/var/spool/cron"
    return owner, group, crontab_dir


def present(
    name,
    user="root",
    minute="*",
    hour="*",
    daymonth="*",
    month="*",
    dayweek="*",
    comment=None,
    commented=False,
    identifier=False,
    special=None,
):
    """
    Verifies that the specified cron job is present for the specified user.
    It is recommended to use `identifier`. Otherwise the cron job is installed
    twice if you change the name.
    For more advanced information about what exactly can be set in the cron
    timing parameters, check your cron system's documentation. Most Unix-like
    systems' cron documentation can be found via the crontab man page:
    ``man 5 crontab``.

    name
        The command that should be executed by the cron job.

    user
        The name of the user whose crontab needs to be modified, defaults to
        the root user

    minute
        The information to be set into the minute section, this can be any
        string supported by your cron system's the minute field. Default is
        ``*``

    hour
        The information to be set in the hour section. Default is ``*``

    daymonth
        The information to be set in the day of month section. Default is ``*``

    month
        The information to be set in the month section. Default is ``*``

    dayweek
        The information to be set in the day of week section. Default is ``*``

    comment
        User comment to be added on line previous the cron job

    commented
        The cron job is set commented (prefixed with ``#DISABLED#``).
        Defaults to False.

        .. versionadded:: 2016.3.0

    identifier
        Custom-defined identifier for tracking the cron line for future crontab
        edits. This defaults to the state name

    special
        A special keyword to specify periodicity (eg. @reboot, @hourly...).
        Quotes must be used, otherwise PyYAML will strip the '@' sign.

        .. versionadded:: 2016.3.0
    """
    name = name.strip()
    if identifier is False:
        identifier = name
    ret = {"changes": {}, "comment": "", "name": name, "result": True}
    if __opts__["test"]:
        status = _check_cron(
            user,
            cmd=name,
            minute=minute,
            hour=hour,
            daymonth=daymonth,
            month=month,
            dayweek=dayweek,
            comment=comment,
            commented=commented,
            identifier=identifier,
            special=special,
        )
        ret["result"] = None
        if status == "absent":
            ret["comment"] = "Cron {} is set to be added".format(name)
        elif status == "present":
            ret["result"] = True
            ret["comment"] = "Cron {} already present".format(name)
        elif status == "update":
            ret["comment"] = "Cron {} is set to be updated".format(name)
        return ret

    if special is None:
        data = __salt__["cron.set_job"](
            user=user,
            minute=minute,
            hour=hour,
            daymonth=daymonth,
            month=month,
            dayweek=dayweek,
            cmd=name,
            comment=comment,
            commented=commented,
            identifier=identifier,
        )
    else:
        data = __salt__["cron.set_special"](
            user=user,
            special=special,
            cmd=name,
            comment=comment,
            commented=commented,
            identifier=identifier,
        )
    if data == "present":
        ret["comment"] = "Cron {} already present".format(name)
        return ret

    if data == "new":
        ret["comment"] = "Cron {} added to {}'s crontab".format(name, user)
        ret["changes"] = {user: name}
        return ret

    if data == "updated":
        ret["comment"] = "Cron {} updated".format(name)
        ret["changes"] = {user: name}
        return ret
    ret["comment"] = "Cron {} for user {} failed to commit with error \n{}".format(
        name, user, data
    )
    ret["result"] = False
    return ret


def absent(name, user="root", identifier=False, special=None, **kwargs):
    """
    Verifies that the specified cron job is absent for the specified user.

    If an ``identifier`` is not passed then the ``name`` is used to identify
    the cron job for removal.

    name
        The command that should be absent in the user crontab.

    user
        The name of the user whose crontab needs to be modified, defaults to
        the root user

    identifier
        Custom-defined identifier for tracking the cron line for future crontab
        edits. This defaults to the state name

    special
        The special keyword used in the job (eg. @reboot, @hourly...).
        Quotes must be used, otherwise PyYAML will strip the '@' sign.
    """
    # NOTE: The keyword arguments in **kwargs are ignored in this state, but
    #       cannot be removed from the function definition, otherwise the use
    #       of unsupported arguments will result in a traceback.

    name = name.strip()
    if identifier is False:
        identifier = name
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    if __opts__["test"]:
        status = _check_cron(user, name, identifier=identifier)
        ret["result"] = None
        if status == "absent":
            ret["result"] = True
            ret["comment"] = "Cron {} is absent".format(name)
        elif status == "present" or status == "update":
            ret["comment"] = "Cron {} is set to be removed".format(name)
        return ret

    if special is None:
        data = __salt__["cron.rm_job"](user, name, identifier=identifier)
    else:
        data = __salt__["cron.rm_special"](
            user, name, special=special, identifier=identifier
        )

    if data == "absent":
        ret["comment"] = "Cron {} already absent".format(name)
        return ret
    if data == "removed":
        ret["comment"] = "Cron {} removed from {}'s crontab".format(name, user)
        ret["changes"] = {user: name}
        return ret
    ret["comment"] = "Cron {} for user {} failed to commit with error {}".format(
        name, user, data
    )
    ret["result"] = False
    return ret


def file(
    name,
    source_hash="",
    source_hash_name=None,
    user="root",
    template=None,
    context=None,
    replace=True,
    defaults=None,
    backup="",
    **kwargs
):
    """
    Provides file.managed-like functionality (templating, etc.) for a pre-made
    crontab file, to be assigned to a given user.

    name
        The source file to be used as the crontab. This source file can be
        hosted on either the salt master server, or on an HTTP or FTP server.
        For files hosted on the salt file server, if the file is located on
        the master in the directory named spam, and is called eggs, the source
        string is ``salt://spam/eggs``

        If the file is hosted on a HTTP or FTP server then the source_hash
        argument is also required

    source_hash
        This can be either a file which contains a source hash string for
        the source, or a source hash string. The source hash string is the
        hash algorithm followed by the hash of the file:
        ``md5=e138491e9d5b97023cea823fe17bac22``

    source_hash_name
        When ``source_hash`` refers to a hash file, Salt will try to find the
        correct hash by matching the filename/URI associated with that hash. By
        default, Salt will look for the filename being managed. When managing a
        file at path ``/tmp/foo.txt``, then the following line in a hash file
        would match:

        .. code-block:: text

            acbd18db4cc2f85cedef654fccc4a4d8    foo.txt

        However, sometimes a hash file will include multiple similar paths:

        .. code-block:: text

            37b51d194a7513e45b56f6524f2d51f2    ./dir1/foo.txt
            acbd18db4cc2f85cedef654fccc4a4d8    ./dir2/foo.txt
            73feffa4b7f6bb68e44cf984c85f6e88    ./dir3/foo.txt

        In cases like this, Salt may match the incorrect hash. This argument
        can be used to tell Salt which filename to match, to ensure that the
        correct hash is identified. For example:

        .. code-block:: yaml

            foo_crontab:
              cron.file:
                - name: https://mydomain.tld/dir2/foo.txt
                - source_hash: https://mydomain.tld/hashes
                - source_hash_name: ./dir2/foo.txt

        .. note::
            This argument must contain the full filename entry from the
            checksum file, as this argument is meant to disambiguate matches
            for multiple files that have the same basename. So, in the
            example above, simply using ``foo.txt`` would not match.

        .. versionadded:: 2016.3.5

    user
        The user to whom the crontab should be assigned. This defaults to
        root.

    template
        If this setting is applied then the named templating engine will be
        used to render the downloaded file. Currently, jinja and mako are
        supported.

    context
        Overrides default context variables passed to the template.

    replace
        If the crontab should be replaced, if False then this command will
        be ignored if a crontab exists for the specified user. Default is True.

    defaults
        Default context passed to the template.

    backup
        Overrides the default backup mode for the user's crontab.
    """
    # Initial set up
    mode = "0600"

    try:
        group = __salt__["user.info"](user)["groups"][0]
    except Exception:  # pylint: disable=broad-except
        ret = {
            "changes": {},
            "comment": "Could not identify group for user {}".format(user),
            "name": name,
            "result": False,
        }
        return ret

    cron_path = salt.utils.files.mkstemp()
    with salt.utils.files.fopen(cron_path, "w+") as fp_:
        raw_cron = __salt__["cron.raw_cron"](user)
        if not raw_cron.endswith("\n"):
            raw_cron = "{}\n".format(raw_cron)
        fp_.write(salt.utils.stringutils.to_str(raw_cron))

    ret = {"changes": {}, "comment": "", "name": name, "result": True}

    # Avoid variable naming confusion in below module calls, since ID
    # declaration for this state will be a source URI.
    source = name

    if not replace and os.stat(cron_path).st_size > 0:
        ret["comment"] = "User {} already has a crontab. No changes made".format(user)
        os.unlink(cron_path)
        return ret

    if __opts__["test"]:
        fcm = __salt__["file.check_managed"](
            name=cron_path,
            source=source,
            source_hash=source_hash,
            source_hash_name=source_hash_name,
            user=user,
            group=group,
            mode=mode,
            attrs=[],  # no special attrs for cron
            template=template,
            context=context,
            defaults=defaults,
            saltenv=__env__,
            **kwargs
        )
        ret["result"], ret["comment"] = fcm
        os.unlink(cron_path)
        return ret

    # If the source is a list then find which file exists
    source, source_hash = __salt__["file.source_list"](source, source_hash, __env__)

    # Gather the source file from the server
    try:
        sfn, source_sum, comment = __salt__["file.get_managed"](
            name=cron_path,
            template=template,
            source=source,
            source_hash=source_hash,
            source_hash_name=source_hash_name,
            user=user,
            group=group,
            mode=mode,
            attrs=[],
            saltenv=__env__,
            context=context,
            defaults=defaults,
            skip_verify=False,  # skip_verify
            **kwargs
        )
    except Exception as exc:  # pylint: disable=broad-except
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = "Unable to manage file: {}".format(exc)
        return ret

    if comment:
        ret["comment"] = comment
        ret["result"] = False
        os.unlink(cron_path)
        return ret

    try:
        ret = __salt__["file.manage_file"](
            name=cron_path,
            sfn=sfn,
            ret=ret,
            source=source,
            source_sum=source_sum,
            user=user,
            group=group,
            mode=mode,
            attrs=[],
            saltenv=__env__,
            backup=backup,
        )
    except Exception as exc:  # pylint: disable=broad-except
        ret["result"] = False
        ret["changes"] = {}
        ret["comment"] = "Unable to manage file: {}".format(exc)
        return ret

    cron_ret = None
    if "diff" in ret["changes"]:
        cron_ret = __salt__["cron.write_cron_file_verbose"](user, cron_path)
        # Check cmd return code and show success or failure
        if cron_ret["retcode"] == 0:
            ret["comment"] = "Crontab for user {} was updated".format(user)
            ret["result"] = True
            ret["changes"] = ret["changes"]
        else:
            ret["comment"] = "Unable to update user {} crontab {}. Error: {}".format(
                user, cron_path, cron_ret["stderr"]
            )
            ret["result"] = False
            ret["changes"] = {}
    elif ret["result"]:
        ret["comment"] = "Crontab for user {} is in the correct state".format(user)
        ret["changes"] = {}

    os.unlink(cron_path)
    return ret


def env_present(name, value=None, user="root"):
    """
    Verifies that the specified environment variable is present in the crontab
    for the specified user.

    name
        The name of the environment variable to set in the user crontab

    user
        The name of the user whose crontab needs to be modified, defaults to
        the root user

    value
        The value to set for the given environment variable
    """
    ret = {"changes": {}, "comment": "", "name": name, "result": True}
    if __opts__["test"]:
        status = _check_cron_env(user, name, value=value)
        ret["result"] = None
        if status == "absent":
            ret["comment"] = "Cron env {} is set to be added".format(name)
        elif status == "present":
            ret["result"] = True
            ret["comment"] = "Cron env {} already present".format(name)
        elif status == "update":
            ret["comment"] = "Cron env {} is set to be updated".format(name)
        return ret

    data = __salt__["cron.set_env"](user, name, value=value)
    if data == "present":
        ret["comment"] = "Cron env {} already present".format(name)
        return ret

    if data == "new":
        ret["comment"] = "Cron env {} added to {}'s crontab".format(name, user)
        ret["changes"] = {user: name}
        return ret

    if data == "updated":
        ret["comment"] = "Cron env {} updated".format(name)
        ret["changes"] = {user: name}
        return ret
    ret["comment"] = "Cron env {} for user {} failed to commit with error \n{}".format(
        name, user, data
    )
    ret["result"] = False
    return ret


def env_absent(name, user="root"):
    """
    Verifies that the specified environment variable is absent from the crontab
    for the specified user

    name
        The name of the environment variable to remove from the user crontab

    user
        The name of the user whose crontab needs to be modified, defaults to
        the root user
    """

    name = name.strip()
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    if __opts__["test"]:
        status = _check_cron_env(user, name)
        ret["result"] = None
        if status == "absent":
            ret["result"] = True
            ret["comment"] = "Cron env {} is absent".format(name)
        elif status == "present" or status == "update":
            ret["comment"] = "Cron env {} is set to be removed".format(name)
        return ret

    data = __salt__["cron.rm_env"](user, name)
    if data == "absent":
        ret["comment"] = "Cron env {} already absent".format(name)
        return ret
    if data == "removed":
        ret["comment"] = "Cron env {} removed from {}'s crontab".format(name, user)
        ret["changes"] = {user: name}
        return ret
    ret["comment"] = "Cron env {} for user {} failed to commit with error {}".format(
        name, user, data
    )
    ret["result"] = False
    return ret
