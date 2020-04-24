# -*- coding: utf-8 -*-
"""
Return data to local job cache

"""
from __future__ import absolute_import, print_function, unicode_literals

import bisect

# Import python libs
import errno
import glob
import logging
import os
import shutil
import time

import salt.exceptions

# Import salt libs
import salt.payload
import salt.utils.atomicfile
import salt.utils.files
import salt.utils.jid
import salt.utils.minions
import salt.utils.msgpack
import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

log = logging.getLogger(__name__)

# load is the published job
LOAD_P = ".load.p"
# the list of minions that the job is targeted to (best effort match on the
# master side)
MINIONS_P = ".minions.p"
# format string for minion lists forwarded from syndic masters (the placeholder
# will be replaced with the syndic master's id)
SYNDIC_MINIONS_P = ".minions.{0}.p"
# return is the "return" from the minion data
RETURN_P = "return.p"
# out is the "out" from the minion data
OUT_P = "out.p"
# endtime is the end time for a job, not stored as msgpack
ENDTIME = "endtime"


def _job_dir():
    """
    Return root of the jobs cache directory
    """
    return os.path.join(__opts__["cachedir"], "jobs")


def _walk_through(job_dir):
    """
    Walk though the jid dir and look for jobs
    """
    serial = salt.payload.Serial(__opts__)

    for top in os.listdir(job_dir):
        t_path = os.path.join(job_dir, top)

        if not os.path.exists(t_path):
            continue

        for final in os.listdir(t_path):
            load_path = os.path.join(t_path, final, LOAD_P)

            if not os.path.isfile(load_path):
                continue

            with salt.utils.files.fopen(load_path, "rb") as rfh:
                try:
                    job = serial.load(rfh)
                except Exception:  # pylint: disable=broad-except
                    log.exception("Failed to deserialize %s", load_path)
                    continue
                if not job:
                    log.error(
                        "Deserialization of job succeded but there is no data in %s",
                        load_path,
                    )
                    continue
                jid = job["jid"]
                yield jid, job, t_path, final


# TODO: add to returner docs-- this is a new one
def prep_jid(nocache=False, passed_jid=None, recurse_count=0):
    """
    Return a job id and prepare the job id directory.

    This is the function responsible for making sure jids don't collide (unless
    it is passed a jid).
    So do what you have to do to make sure that stays the case
    """
    if recurse_count >= 5:
        err = "prep_jid could not store a jid after {0} tries.".format(recurse_count)
        log.error(err)
        raise salt.exceptions.SaltCacheError(err)
    if passed_jid is None:  # this can be a None or an empty string.
        jid = salt.utils.jid.gen_jid(__opts__)
    else:
        jid = passed_jid

    jid_dir = salt.utils.jid.jid_dir(jid, _job_dir(), __opts__["hash_type"])

    # Make sure we create the jid dir, otherwise someone else is using it,
    # meaning we need a new jid.
    if not os.path.isdir(jid_dir):
        try:
            os.makedirs(jid_dir)
        except OSError:
            time.sleep(0.1)
            if passed_jid is None:
                return prep_jid(nocache=nocache, recurse_count=recurse_count + 1)

    try:
        with salt.utils.files.fopen(os.path.join(jid_dir, "jid"), "wb+") as fn_:
            fn_.write(salt.utils.stringutils.to_bytes(jid))
        if nocache:
            with salt.utils.files.fopen(os.path.join(jid_dir, "nocache"), "wb+"):
                pass
    except IOError:
        log.warning("Could not write out jid file for job %s. Retrying.", jid)
        time.sleep(0.1)
        return prep_jid(
            passed_jid=jid, nocache=nocache, recurse_count=recurse_count + 1
        )

    return jid


def returner(load):
    """
    Return data to the local job cache
    """
    serial = salt.payload.Serial(__opts__)

    # if a minion is returning a standalone job, get a jobid
    if load["jid"] == "req":
        load["jid"] = prep_jid(nocache=load.get("nocache", False))

    jid_dir = salt.utils.jid.jid_dir(load["jid"], _job_dir(), __opts__["hash_type"])
    if os.path.exists(os.path.join(jid_dir, "nocache")):
        return

    hn_dir = os.path.join(jid_dir, load["id"])

    try:
        os.makedirs(hn_dir)
    except OSError as err:
        if err.errno == errno.EEXIST:
            # Minion has already returned this jid and it should be dropped
            log.error(
                "An extra return was detected from minion %s, please verify "
                "the minion, this could be a replay attack",
                load["id"],
            )
            return False
        elif err.errno == errno.ENOENT:
            log.error(
                "An inconsistency occurred, a job was received with a job id "
                "(%s) that is not present in the local cache",
                load["jid"],
            )
            return False
        raise

    serial.dump(
        dict(
            (key, load[key]) for key in ["return", "retcode", "success"] if key in load
        ),
        # Use atomic open here to avoid the file being read before it's
        # completely written to. Refs #1935
        salt.utils.atomicfile.atomic_open(os.path.join(hn_dir, RETURN_P), "w+b"),
    )

    if "out" in load:
        serial.dump(
            load["out"],
            # Use atomic open here to avoid the file being read before
            # it's completely written to. Refs #1935
            salt.utils.atomicfile.atomic_open(os.path.join(hn_dir, OUT_P), "w+b"),
        )


def save_load(jid, clear_load, minions=None, recurse_count=0):
    """
    Save the load to the specified jid

    minions argument is to provide a pre-computed list of matched minions for
    the job, for cases when this function can't compute that list itself (such
    as for salt-ssh)
    """
    if recurse_count >= 5:
        err = "save_load could not write job cache file after {0} retries.".format(
            recurse_count
        )
        log.error(err)
        raise salt.exceptions.SaltCacheError(err)

    jid_dir = salt.utils.jid.jid_dir(jid, _job_dir(), __opts__["hash_type"])

    serial = salt.payload.Serial(__opts__)

    # Save the invocation information
    try:
        if not os.path.exists(jid_dir):
            os.makedirs(jid_dir)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            # rarely, the directory can be already concurrently created between
            # the os.path.exists and the os.makedirs lines above
            pass
        else:
            raise
    try:
        with salt.utils.files.fopen(os.path.join(jid_dir, LOAD_P), "w+b") as wfh:
            serial.dump(clear_load, wfh)
    except IOError as exc:
        log.warning("Could not write job invocation cache file: %s", exc)
        time.sleep(0.1)
        return save_load(
            jid=jid, clear_load=clear_load, recurse_count=recurse_count + 1
        )

    # if you have a tgt, save that for the UI etc
    if "tgt" in clear_load and clear_load["tgt"] != "":
        if minions is None:
            ckminions = salt.utils.minions.CkMinions(__opts__)
            # Retrieve the minions list
            _res = ckminions.check_minions(
                clear_load["tgt"], clear_load.get("tgt_type", "glob")
            )
            minions = _res["minions"]
        # save the minions to a cache so we can see in the UI
        save_minions(jid, minions)


def save_minions(jid, minions, syndic_id=None):
    """
    Save/update the serialized list of minions for a given job
    """
    # Ensure we have a list for Python 3 compatability
    minions = list(minions)

    log.debug(
        "Adding minions for job %s%s: %s",
        jid,
        " from syndic master '{0}'".format(syndic_id) if syndic_id else "",
        minions,
    )
    serial = salt.payload.Serial(__opts__)

    jid_dir = salt.utils.jid.jid_dir(jid, _job_dir(), __opts__["hash_type"])

    try:
        if not os.path.exists(jid_dir):
            os.makedirs(jid_dir)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            # rarely, the directory can be already concurrently created between
            # the os.path.exists and the os.makedirs lines above
            pass
        else:
            raise

    if syndic_id is not None:
        minions_path = os.path.join(jid_dir, SYNDIC_MINIONS_P.format(syndic_id))
    else:
        minions_path = os.path.join(jid_dir, MINIONS_P)

    try:
        if not os.path.exists(jid_dir):
            try:
                os.makedirs(jid_dir)
            except OSError:
                pass
        with salt.utils.files.fopen(minions_path, "w+b") as wfh:
            serial.dump(minions, wfh)
    except IOError as exc:
        log.error(
            "Failed to write minion list %s to job cache file %s: %s",
            minions,
            minions_path,
            exc,
        )


def get_load(jid):
    """
    Return the load data that marks a specified jid
    """
    jid_dir = salt.utils.jid.jid_dir(jid, _job_dir(), __opts__["hash_type"])
    load_fn = os.path.join(jid_dir, LOAD_P)
    if not os.path.exists(jid_dir) or not os.path.exists(load_fn):
        return {}
    serial = salt.payload.Serial(__opts__)
    ret = {}
    load_p = os.path.join(jid_dir, LOAD_P)
    num_tries = 5
    for index in range(1, num_tries + 1):
        with salt.utils.files.fopen(load_p, "rb") as rfh:
            try:
                ret = serial.load(rfh)
                break
            except Exception as exc:  # pylint: disable=broad-except
                if index == num_tries:
                    time.sleep(0.25)
    else:
        log.critical("Failed to unpack %s", load_p)
        raise exc
    if ret is None:
        ret = {}
    minions_cache = [os.path.join(jid_dir, MINIONS_P)]
    minions_cache.extend(glob.glob(os.path.join(jid_dir, SYNDIC_MINIONS_P.format("*"))))
    all_minions = set()
    for minions_path in minions_cache:
        log.debug("Reading minion list from %s", minions_path)
        try:
            with salt.utils.files.fopen(minions_path, "rb") as rfh:
                all_minions.update(serial.load(rfh))
        except IOError as exc:
            salt.utils.files.process_read_exception(exc, minions_path)

    if all_minions:
        ret["Minions"] = sorted(all_minions)

    return ret


def get_jid(jid):
    """
    Return the information returned when the specified job id was executed
    """
    jid_dir = salt.utils.jid.jid_dir(jid, _job_dir(), __opts__["hash_type"])
    serial = salt.payload.Serial(__opts__)

    ret = {}
    # Check to see if the jid is real, if not return the empty dict
    if not os.path.isdir(jid_dir):
        return ret
    for fn_ in os.listdir(jid_dir):
        if fn_.startswith("."):
            continue
        if fn_ not in ret:
            retp = os.path.join(jid_dir, fn_, RETURN_P)
            outp = os.path.join(jid_dir, fn_, OUT_P)
            if not os.path.isfile(retp):
                continue
            while fn_ not in ret:
                try:
                    with salt.utils.files.fopen(retp, "rb") as rfh:
                        ret_data = serial.load(rfh)
                    if not isinstance(ret_data, dict) or "return" not in ret_data:
                        # Convert the old format in which return.p contains the only return data to
                        # the new that is dict containing 'return' and optionally 'retcode' and
                        # 'success'.
                        ret_data = {"return": ret_data}
                    ret[fn_] = ret_data
                    if os.path.isfile(outp):
                        with salt.utils.files.fopen(outp, "rb") as rfh:
                            ret[fn_]["out"] = serial.load(rfh)
                except Exception as exc:  # pylint: disable=broad-except
                    if "Permission denied:" in six.text_type(exc):
                        raise
    return ret


def get_jids():
    """
    Return a dict mapping all job ids to job information
    """
    ret = {}
    for jid, job, _, _ in _walk_through(_job_dir()):
        ret[jid] = salt.utils.jid.format_jid_instance(jid, job)

        if __opts__.get("job_cache_store_endtime"):
            endtime = get_endtime(jid)
            if endtime:
                ret[jid]["EndTime"] = endtime

    return ret


def get_jids_filter(count, filter_find_job=True):
    """
    Return a list of all jobs information filtered by the given criteria.
    :param int count: show not more than the count of most recent jobs
    :param bool filter_find_jobs: filter out 'saltutil.find_job' jobs
    """
    keys = []
    ret = []
    for jid, job, _, _ in _walk_through(_job_dir()):
        job = salt.utils.jid.format_jid_instance_ext(jid, job)
        if filter_find_job and job["Function"] == "saltutil.find_job":
            continue
        i = bisect.bisect(keys, jid)
        if len(keys) == count and i == 0:
            continue
        keys.insert(i, jid)
        ret.insert(i, job)
        if len(keys) > count:
            del keys[0]
            del ret[0]
    return ret


def clean_old_jobs():
    """
    Clean out the old jobs from the job cache
    """
    if __opts__["keep_jobs"] != 0:
        jid_root = _job_dir()

        if not os.path.exists(jid_root):
            return

        # Keep track of any empty t_path dirs that need to be removed later
        dirs_to_remove = set()

        for top in os.listdir(jid_root):
            t_path = os.path.join(jid_root, top)

            if not os.path.exists(t_path):
                continue

            # Check if there are any stray/empty JID t_path dirs
            t_path_dirs = os.listdir(t_path)
            if not t_path_dirs and t_path not in dirs_to_remove:
                dirs_to_remove.add(t_path)
                continue

            for final in t_path_dirs:
                f_path = os.path.join(t_path, final)
                jid_file = os.path.join(f_path, "jid")
                if not os.path.isfile(jid_file) and os.path.exists(f_path):
                    # No jid file means corrupted cache entry, scrub it
                    # by removing the entire f_path directory
                    shutil.rmtree(f_path)
                elif os.path.isfile(jid_file):
                    jid_ctime = os.stat(jid_file).st_ctime
                    hours_difference = (time.time() - jid_ctime) / 3600.0
                    if hours_difference > __opts__["keep_jobs"] and os.path.exists(
                        t_path
                    ):
                        # Remove the entire f_path from the original JID dir
                        try:
                            shutil.rmtree(f_path)
                        except OSError as err:
                            log.error("Unable to remove %s: %s", f_path, err)

        # Remove empty JID dirs from job cache, if they're old enough.
        # JID dirs may be empty either from a previous cache-clean with the bug
        # Listed in #29286 still present, or the JID dir was only recently made
        # And the jid file hasn't been created yet.
        if dirs_to_remove:
            for t_path in dirs_to_remove:
                # Checking the time again prevents a possible race condition where
                # t_path JID dirs were created, but not yet populated by a jid file.
                t_path_ctime = os.stat(t_path).st_ctime
                hours_difference = (time.time() - t_path_ctime) / 3600.0
                if hours_difference > __opts__["keep_jobs"]:
                    shutil.rmtree(t_path)


def update_endtime(jid, time):
    """
    Update (or store) the end time for a given job

    Endtime is stored as a plain text string
    """
    jid_dir = salt.utils.jid.jid_dir(jid, _job_dir(), __opts__["hash_type"])
    try:
        if not os.path.exists(jid_dir):
            os.makedirs(jid_dir)
        with salt.utils.files.fopen(os.path.join(jid_dir, ENDTIME), "w") as etfile:
            etfile.write(salt.utils.stringutils.to_str(time))
    except IOError as exc:
        log.warning("Could not write job invocation cache file: %s", exc)


def get_endtime(jid):
    """
    Retrieve the stored endtime for a given job

    Returns False if no endtime is present
    """
    jid_dir = salt.utils.jid.jid_dir(jid, _job_dir(), __opts__["hash_type"])
    etpath = os.path.join(jid_dir, ENDTIME)
    if not os.path.exists(etpath):
        return False
    with salt.utils.files.fopen(etpath, "r") as etfile:
        endtime = salt.utils.stringutils.to_unicode(etfile.read()).strip("\n")
    return endtime


def _reg_dir():
    """
    Return the reg_dir for the given job id
    """
    return os.path.join(__opts__["cachedir"], "thorium")


def save_reg(data):
    """
    Save the register to msgpack files
    """
    reg_dir = _reg_dir()
    regfile = os.path.join(reg_dir, "register")
    try:
        if not os.path.exists(reg_dir):
            os.makedirs(reg_dir)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            pass
        else:
            raise
    try:
        with salt.utils.files.fopen(regfile, "a") as fh_:
            salt.utils.msgpack.dump(data, fh_)
    except Exception:  # pylint: disable=broad-except
        log.error("Could not write to msgpack file %s", __opts__["outdir"])
        raise


def load_reg():
    """
    Load the register from msgpack files
    """
    reg_dir = _reg_dir()
    regfile = os.path.join(reg_dir, "register")
    try:
        with salt.utils.files.fopen(regfile, "r") as fh_:
            return salt.utils.msgpack.load(fh_)
    except Exception:  # pylint: disable=broad-except
        log.error("Could not write to msgpack file %s", __opts__["outdir"])
        raise
