# -*- coding: utf-8 -*-
'''
Utility functions for minions
'''

# Import Python Libs
from __future__ import absolute_import
import os
import logging
import threading

# Import Salt Libs
import salt.utils
import salt.payload

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)


def running(opts):
    '''
    Return the running jobs on this minion
    '''

    ret = []
    proc_dir = os.path.join(opts['cachedir'], 'proc')
    if not os.path.isdir(proc_dir):
        return ret
    for fn_ in os.listdir(proc_dir):
        path = os.path.join(proc_dir, fn_)
        try:
            data = _read_proc_file(path, opts)
            if data is not None:
                ret.append(data)
        except (IOError, OSError):
            # proc files may be removed at any time during this process by
            # the minion process that is executing the JID in question, so
            # we must ignore ENOENT during this process
            pass
    return ret


def cache_jobs(opts, jid, ret):
    serial = salt.payload.Serial(opts=opts)

    fn_ = os.path.join(
        opts['cachedir'],
        'minion_jobs',
        jid,
        'return.p')
    jdir = os.path.dirname(fn_)
    if not os.path.isdir(jdir):
        os.makedirs(jdir)
    with salt.utils.fopen(fn_, 'w+b') as fp_:
        fp_.write(serial.dumps(ret))


def _read_proc_file(path, opts):
    '''
    Return a dict of JID metadata, or None
    '''
    serial = salt.payload.Serial(opts)
    current_thread = threading.currentThread().name
    pid = os.getpid()
    with salt.utils.fopen(path, 'rb') as fp_:
        buf = fp_.read()
        fp_.close()
        if buf:
            data = serial.loads(buf)
        else:
            # Proc file is empty, remove
            try:
                os.remove(path)
            except IOError:
                pass
            return None
    if not isinstance(data, dict):
        # Invalid serial object
        return None
    if not salt.utils.process.os_is_running(data['pid']):
        # The process is no longer running, clear out the file and
        # continue
        try:
            os.remove(path)
        except IOError:
            pass
        return None
    if opts.get('multiprocessing'):
        if data.get('pid') == pid:
            return None
    else:
        if data.get('pid') != pid:
            try:
                os.remove(path)
            except IOError:
                pass
            return None
        if data.get('jid') == current_thread:
            return None
        if not data.get('jid') in [x.name for x in threading.enumerate()]:
            try:
                os.remove(path)
            except IOError:
                pass
            return None

    if not _check_cmdline(data):
        pid = data.get('pid')
        if pid:
            log.warning(
                'PID {0} exists but does not appear to be a salt process.'.format(pid)
            )
        try:
            os.remove(path)
        except IOError:
            pass
        return None
    return data


def _check_cmdline(data):
    '''
    In some cases where there are an insane number of processes being created
    on a system a PID can get recycled or assigned to a non-Salt process.
    On Linux this fn checks to make sure the PID we are checking on is actually
    a Salt process.

    For non-Linux systems we punt and just return True
    '''
    if not salt.utils.is_linux():
        return True
    pid = data.get('pid')
    if not pid:
        return False
    if not os.path.isdir('/proc'):
        return True
    path = os.path.join('/proc/{0}/cmdline'.format(pid))
    if not os.path.isfile(path):
        return False
    try:
        with salt.utils.fopen(path, 'rb') as fp_:
            if six.b('salt') in fp_.read():
                return True
    except (OSError, IOError):
        return False
