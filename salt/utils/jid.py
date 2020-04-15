# -*- coding: utf-8 -*-
"""
Functions for creating and working with job IDs
"""
from __future__ import absolute_import, print_function, unicode_literals

import datetime
import hashlib
import os
from calendar import month_abbr as months

import salt.utils.stringutils
from salt.ext import six

LAST_JID_DATETIME = None


def _utc_now():
    """
    Helper method so tests do not have to patch the built-in method.
    """
    return datetime.datetime.utcnow()


def gen_jid(opts=None):
    """
    Generate a jid
    """
    if opts is None:
        salt.utils.versions.warn_until(
            "Sodium",
            "The `opts` argument was not passed into salt.utils.jid.gen_jid(). "
            "This will be required starting in {version}.",
        )
        opts = {}
    global LAST_JID_DATETIME  # pylint: disable=global-statement

    jid_dt = _utc_now()
    if not opts.get("unique_jid", False):
        return "{0:%Y%m%d%H%M%S%f}".format(jid_dt)
    if LAST_JID_DATETIME and LAST_JID_DATETIME >= jid_dt:
        jid_dt = LAST_JID_DATETIME + datetime.timedelta(microseconds=1)
    LAST_JID_DATETIME = jid_dt
    return "{0:%Y%m%d%H%M%S%f}_{1}".format(jid_dt, os.getpid())


def is_jid(jid):
    """
    Returns True if the passed in value is a job id
    """
    if not isinstance(jid, six.string_types):
        return False
    if len(jid) != 20 and (len(jid) <= 21 or jid[20] != "_"):
        return False
    try:
        int(jid[:20])
        return True
    except ValueError:
        return False


def jid_to_time(jid):
    """
    Convert a salt job id into the time when the job was invoked
    """
    jid = six.text_type(jid)
    if len(jid) != 20 and (len(jid) <= 21 or jid[20] != "_"):
        return ""
    year = jid[:4]
    month = jid[4:6]
    day = jid[6:8]
    hour = jid[8:10]
    minute = jid[10:12]
    second = jid[12:14]
    micro = jid[14:20]

    ret = "{0}, {1} {2} {3}:{4}:{5}.{6}".format(
        year, months[int(month)], day, hour, minute, second, micro
    )
    return ret


def format_job_instance(job):
    """
    Format the job instance correctly
    """
    ret = {
        "Function": job.get("fun", "unknown-function"),
        "Arguments": list(job.get("arg", [])),
        # unlikely but safeguard from invalid returns
        "Target": job.get("tgt", "unknown-target"),
        "Target-type": job.get("tgt_type", "list"),
        "User": job.get("user", "root"),
    }

    if "metadata" in job:
        ret["Metadata"] = job.get("metadata", {})
    else:
        if "kwargs" in job:
            if "metadata" in job["kwargs"]:
                ret["Metadata"] = job["kwargs"].get("metadata", {})
    return ret


def format_jid_instance(jid, job):
    """
    Format the jid correctly
    """
    ret = format_job_instance(job)
    ret.update({"StartTime": jid_to_time(jid)})
    return ret


def format_jid_instance_ext(jid, job):
    """
    Format the jid correctly with jid included
    """
    ret = format_job_instance(job)
    ret.update({"JID": jid, "StartTime": jid_to_time(jid)})
    return ret


def jid_dir(jid, job_dir=None, hash_type="sha256"):
    """
    Return the jid_dir for the given job id
    """
    if not isinstance(jid, six.string_types):
        jid = six.text_type(jid)
    jhash = getattr(hashlib, hash_type)(
        salt.utils.stringutils.to_bytes(jid)
    ).hexdigest()

    parts = []
    if job_dir is not None:
        parts.append(job_dir)
    parts.extend([jhash[:2], jhash[2:]])
    return os.path.join(*parts)
