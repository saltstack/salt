"""
Utility functions for minions
"""

import logging
import os
import threading

import salt.payload
import salt.utils.files
import salt.utils.platform
import salt.utils.process

log = logging.getLogger(__name__)


def running(opts):
    """
    Return the running jobs on this minion
    """

    ret = []
    proc_dir = os.path.join(opts["cachedir"], "proc")
    if not os.path.isdir(proc_dir):
        return ret
    for fn_ in os.listdir(proc_dir):
        path = os.path.join(proc_dir, fn_)
        try:
            data = _read_proc_file(path, opts)
            if data is not None:
                ret.append(data)
        except OSError:
            # proc files may be removed at any time during this process by
            # the minion process that is executing the JID in question, so
            # we must ignore ENOENT during this process
            pass
    return ret


def cache_jobs(opts, jid, ret):
    """
    Write job information to cache
    """
    fn_ = os.path.join(opts["cachedir"], "minion_jobs", jid, "return.p")
    jdir = os.path.dirname(fn_)
    if not os.path.isdir(jdir):
        os.makedirs(jdir)
    with salt.utils.files.fopen(fn_, "w+b") as fp_:
        fp_.write(salt.payload.dumps(ret))


def _read_proc_file(path, opts):
    """
    Return a dict of JID metadata, or None
    """
    current_thread = threading.current_thread().name
    pid = os.getpid()
    with salt.utils.files.fopen(path, "rb") as fp_:
        buf = fp_.read()
        fp_.close()
        if buf:
            data = salt.payload.loads(buf)
        else:
            # Proc file is empty, remove
            try:
                os.remove(path)
            except OSError:
                log.debug("Unable to remove proc file %s.", path)
            return None
    if not isinstance(data, dict):
        # Invalid serial object
        return None
    if not salt.utils.process.os_is_running(data["pid"]):
        # The process is no longer running, clear out the file and
        # continue
        try:
            os.remove(path)
        except OSError:
            log.debug("Unable to remove proc file %s.", path)
        return None
    if opts.get("multiprocessing"):
        if data.get("pid") == pid:
            return None
    else:
        if data.get("pid") != pid:
            try:
                os.remove(path)
            except OSError:
                log.debug("Unable to remove proc file %s.", path)
            return None
        thread_name = "{}-Job-{}".format(data.get("jid"), data.get("jid"))
        if data.get("jid") == current_thread or thread_name == current_thread:
            return None
        found = data.get("jid") in [
            x.name for x in threading.enumerate()
        ] or thread_name in [x.name for x in threading.enumerate()]
        if not found:
            found = thread_name in [x.name for x in threading.enumerate()]
        if not found:
            try:
                os.remove(path)
            except OSError:
                log.debug("Unable to remove proc file %s.", path)
            return None

    if not _check_cmdline(data):
        pid = data.get("pid")
        if pid:
            log.warning("PID %s exists but does not appear to be a salt process.", pid)
        try:
            os.remove(path)
        except OSError:
            log.debug("Unable to remove proc file %s.", path)
        return None
    return data


def _check_cmdline(data):
    """
    In some cases where there are an insane number of processes being created
    on a system a PID can get recycled or assigned to a non-Salt process.
    On Linux this fn checks to make sure the PID we are checking on is actually
    a Salt process.

    For non-Linux systems we punt and just return True
    """
    if not salt.utils.platform.is_linux():
        return True
    pid = data.get("pid")
    if not pid:
        return False
    if not os.path.isdir("/proc"):
        return True
    path = os.path.join(f"/proc/{pid}/cmdline")
    if not os.path.isfile(path):
        return False
    try:
        with salt.utils.files.fopen(path, "rb") as fp_:
            return b"salt" in fp_.read()
    except OSError:
        return False
