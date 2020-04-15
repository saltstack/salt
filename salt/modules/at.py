# -*- coding: utf-8 -*-
"""
Wrapper module for at(1)

Also, a 'tag' feature has been added to more
easily tag jobs.

:platform:      linux,openbsd,freebsd

.. versionchanged:: 2017.7.0
"""
from __future__ import absolute_import, print_function, unicode_literals

import datetime

# Import python libs
import re
import time

# Import salt libs
import salt.utils.data
import salt.utils.path
import salt.utils.platform

# pylint: enable=import-error,redefined-builtin
from salt.exceptions import CommandNotFoundError
from salt.ext import six

# Import 3rd-party libs
# pylint: disable=import-error,redefined-builtin
from salt.ext.six.moves import map

# OS Families that should work (Ubuntu and Debian are the default)
# TODO: Refactor some of this module to remove the checks for binaries

# Tested on OpenBSD 5.0
BSD = ("OpenBSD", "FreeBSD")

__virtualname__ = "at"


def __virtual__():
    """
    Most everything has the ability to support at(1)
    """
    if salt.utils.platform.is_windows() or salt.utils.platform.is_sunos():
        return (False, "The at module could not be loaded: unsupported platform")
    if salt.utils.path.which("at") is None:
        return (False, "The at module could not be loaded: at command not found")
    return __virtualname__


def _cmd(binary, *args):
    """
    Wrapper to run at(1) or return None.
    """
    binary = salt.utils.path.which(binary)
    if not binary:
        raise CommandNotFoundError("{0}: command not found".format(binary))
    cmd = [binary] + list(args)
    return __salt__["cmd.run_stdout"]([binary] + list(args), python_shell=False)


def atq(tag=None):
    """
    List all queued and running jobs or only those with
    an optional 'tag'.

    CLI Example:

    .. code-block:: bash

        salt '*' at.atq
        salt '*' at.atq [tag]
        salt '*' at.atq [job number]
    """
    jobs = []

    # Shim to produce output similar to what __virtual__() should do
    # but __salt__ isn't available in __virtual__()
    # Tested on CentOS 5.8
    if __grains__["os_family"] == "RedHat":
        output = _cmd("at", "-l")
    else:
        output = _cmd("atq")

    if output is None:
        return "'at.atq' is not available."

    # No jobs so return
    if output == "":
        return {"jobs": jobs}

    # Jobs created with at.at() will use the following
    # comment to denote a tagged job.
    job_kw_regex = re.compile(r"^### SALT: (\w+)")

    # Split each job into a dictionary and handle
    # pulling out tags or only listing jobs with a certain
    # tag
    for line in output.splitlines():
        job_tag = ""

        # Redhat/CentOS
        if __grains__["os_family"] == "RedHat":
            job, spec = line.split("\t")
            specs = spec.split()
        elif __grains__["os"] == "OpenBSD":
            if line.startswith(" Rank"):
                continue
            else:
                tmp = line.split()
                timestr = " ".join(tmp[1:5])
                job = tmp[6]
                specs = (
                    datetime.datetime(
                        *(time.strptime(timestr, "%b %d, %Y " "%H:%M")[0:5])
                    )
                    .isoformat()
                    .split("T")
                )
                specs.append(tmp[7])
                specs.append(tmp[5])
        elif __grains__["os"] == "FreeBSD":
            if line.startswith("Date"):
                continue
            else:
                tmp = line.split()
                timestr = " ".join(tmp[1:6])
                job = tmp[8]
                specs = (
                    datetime.datetime(
                        *(time.strptime(timestr, "%b %d %H:%M:%S %Z %Y")[0:5])
                    )
                    .isoformat()
                    .split("T")
                )
                specs.append(tmp[7])
                specs.append(tmp[6])

        else:
            job, spec = line.split("\t")
            tmp = spec.split()
            timestr = " ".join(tmp[0:5])
            specs = (
                datetime.datetime(*(time.strptime(timestr)[0:5])).isoformat().split("T")
            )
            specs.append(tmp[5])
            specs.append(tmp[6])

        # Search for any tags
        atc_out = _cmd("at", "-c", job)
        for line in atc_out.splitlines():
            tmp = job_kw_regex.match(line)
            if tmp:
                job_tag = tmp.groups()[0]

        if __grains__["os"] in BSD:
            job = six.text_type(job)
        else:
            job = int(job)

        # If a tag is supplied, only list jobs with that tag
        if tag:
            # TODO: Looks like there is a difference between salt and salt-call
            # If I don't wrap job in an int(), it fails on salt but works on
            # salt-call. With the int(), it fails with salt-call but not salt.
            if tag == job_tag or tag == job:
                jobs.append(
                    {
                        "job": job,
                        "date": specs[0],
                        "time": specs[1],
                        "queue": specs[2],
                        "user": specs[3],
                        "tag": job_tag,
                    }
                )
        else:
            jobs.append(
                {
                    "job": job,
                    "date": specs[0],
                    "time": specs[1],
                    "queue": specs[2],
                    "user": specs[3],
                    "tag": job_tag,
                }
            )

    return {"jobs": jobs}


def atrm(*args):
    """
    Remove jobs from the queue.

    CLI Example:

    .. code-block:: bash

        salt '*' at.atrm <jobid> <jobid> .. <jobid>
        salt '*' at.atrm all
        salt '*' at.atrm all [tag]
    """

    # Need to do this here also since we use atq()
    if not salt.utils.path.which("at"):
        return "'at.atrm' is not available."

    if not args:
        return {"jobs": {"removed": [], "tag": None}}

    # Convert all to strings
    args = salt.utils.data.stringify(args)

    if args[0] == "all":
        if len(args) > 1:
            opts = list(list(map(str, [j["job"] for j in atq(args[1])["jobs"]])))
            ret = {"jobs": {"removed": opts, "tag": args[1]}}
        else:
            opts = list(list(map(str, [j["job"] for j in atq()["jobs"]])))
            ret = {"jobs": {"removed": opts, "tag": None}}
    else:
        opts = list(
            list(
                map(
                    str,
                    [
                        i["job"]
                        for i in atq()["jobs"]
                        if six.text_type(i["job"]) in args
                    ],
                )
            )
        )
        ret = {"jobs": {"removed": opts, "tag": None}}

    # Shim to produce output similar to what __virtual__() should do
    # but __salt__ isn't available in __virtual__()
    output = _cmd("at", "-d", " ".join(opts))
    if output is None:
        return "'at.atrm' is not available."

    return ret


def at(*args, **kwargs):  # pylint: disable=C0103
    """
    Add a job to the queue.

    The 'timespec' follows the format documented in the
    at(1) manpage.

    CLI Example:

    .. code-block:: bash

        salt '*' at.at <timespec> <cmd> [tag=<tag>] [runas=<user>]
        salt '*' at.at 12:05am '/sbin/reboot' tag=reboot
        salt '*' at.at '3:05am +3 days' 'bin/myscript' tag=nightly runas=jim
    """

    if len(args) < 2:
        return {"jobs": []}

    # Shim to produce output similar to what __virtual__() should do
    # but __salt__ isn't available in __virtual__()
    binary = salt.utils.path.which("at")
    if not binary:
        return "'at.at' is not available."

    if "tag" in kwargs:
        stdin = "### SALT: {0}\n{1}".format(kwargs["tag"], " ".join(args[1:]))
    else:
        stdin = " ".join(args[1:])
    cmd = [binary, args[0]]

    cmd_kwargs = {"stdin": stdin, "python_shell": False}
    if "runas" in kwargs:
        cmd_kwargs["runas"] = kwargs["runas"]
    output = __salt__["cmd.run"](cmd, **cmd_kwargs)

    if output is None:
        return "'at.at' is not available."

    if output.endswith("Garbled time"):
        return {"jobs": [], "error": "invalid timespec"}

    if output.startswith("warning: commands"):
        output = output.splitlines()[1]

    if output.startswith("commands will be executed"):
        output = output.splitlines()[1]

    output = output.split()[1]

    if __grains__["os"] in BSD:
        return atq(six.text_type(output))
    else:
        return atq(int(output))


def atc(jobid):
    """
    Print the at(1) script that will run for the passed job
    id. This is mostly for debugging so the output will
    just be text.

    CLI Example:

    .. code-block:: bash

        salt '*' at.atc <jobid>
    """
    # Shim to produce output similar to what __virtual__() should do
    # but __salt__ isn't available in __virtual__()
    output = _cmd("at", "-c", six.text_type(jobid))

    if output is None:
        return "'at.atc' is not available."
    elif output == "":
        return {"error": "invalid job id '{0}'".format(jobid)}

    return output


def _atq(**kwargs):
    """
    Return match jobs list
    """

    jobs = []

    runas = kwargs.get("runas", None)
    tag = kwargs.get("tag", None)
    hour = kwargs.get("hour", None)
    minute = kwargs.get("minute", None)
    day = kwargs.get("day", None)
    month = kwargs.get("month", None)
    year = kwargs.get("year", None)
    if year and len(six.text_type(year)) == 2:
        year = "20{0}".format(year)

    jobinfo = atq()["jobs"]
    if not jobinfo:
        return {"jobs": jobs}

    for job in jobinfo:

        if not runas:
            pass
        elif runas == job["user"]:
            pass
        else:
            continue

        if not tag:
            pass
        elif tag == job["tag"]:
            pass
        else:
            continue

        if not hour:
            pass
        elif "{0:02d}".format(int(hour)) == job["time"].split(":")[0]:
            pass
        else:
            continue

        if not minute:
            pass
        elif "{0:02d}".format(int(minute)) == job["time"].split(":")[1]:
            pass
        else:
            continue

        if not day:
            pass
        elif "{0:02d}".format(int(day)) == job["date"].split("-")[2]:
            pass
        else:
            continue

        if not month:
            pass
        elif "{0:02d}".format(int(month)) == job["date"].split("-")[1]:
            pass
        else:
            continue

        if not year:
            pass
        elif year == job["date"].split("-")[0]:
            pass
        else:
            continue

        jobs.append(job)

    if not jobs:
        note = "No match jobs or time format error"
        return {"jobs": jobs, "note": note}

    return {"jobs": jobs}


def jobcheck(**kwargs):
    """
    Check the job from queue.
    The kwargs dict include 'hour minute day month year tag runas'
    Other parameters will be ignored.

    CLI Example:

    .. code-block:: bash

        salt '*' at.jobcheck runas=jam day=13
        salt '*' at.jobcheck day=13 month=12 year=13 tag=rose
    """

    if not kwargs:
        return {"error": "You have given a condition"}

    return _atq(**kwargs)
