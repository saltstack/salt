# -*- coding: utf-8 -*-
'''
Return data to local job cache

'''
from __future__ import absolute_import

# Import python libs
import errno
import logging
import os
import shutil
import datetime
import hashlib
import time

# Import salt libs
import salt.payload
import salt.utils
import salt.utils.jid
import salt.exceptions

log = logging.getLogger(__name__)

# load is the published job
LOAD_P = '.load.p'
# the list of minions that the job is targeted to (best effort match on the master side)
MINIONS_P = '.minions.p'
# return is the "return" from the minion data
RETURN_P = 'return.p'
# out is the "out" from the minion data
OUT_P = 'out.p'


def _job_dir():
    '''
    Return root of the jobs cache directory
    '''
    return os.path.join(__opts__['cachedir'],
                        'jobs')


def _jid_dir(jid):
    '''
    Return the jid_dir for the given job id
    '''
    jid = str(jid)
    jhash = getattr(hashlib, __opts__['hash_type'])(jid).hexdigest()
    return os.path.join(_job_dir(),
                        jhash[:2],
                        jhash[2:])


def _walk_through(job_dir):
    '''
    Walk though the jid dir and look for jobs
    '''
    serial = salt.payload.Serial(__opts__)

    for top in os.listdir(job_dir):
        t_path = os.path.join(job_dir, top)

        for final in os.listdir(t_path):
            load_path = os.path.join(t_path, final, LOAD_P)

            if not os.path.isfile(load_path):
                continue

            job = serial.load(salt.utils.fopen(load_path, 'rb'))
            jid = job['jid']
            yield jid, job, t_path, final


def _format_job_instance(job):
    '''
    Format the job instance correctly
    '''
    ret = {'Function': job.get('fun', 'unknown-function'),
           'Arguments': list(job.get('arg', [])),
           # unlikely but safeguard from invalid returns
           'Target': job.get('tgt', 'unknown-target'),
           'Target-type': job.get('tgt_type', []),
           'User': job.get('user', 'root')}

    if 'metadata' in job:
        ret['Metadata'] = job.get('metadata', {})
    else:
        if 'kwargs' in job:
            if 'metadata' in job['kwargs']:
                ret['Metadata'] = job['kwargs'].get('metadata', {})
    return ret


def _format_jid_instance(jid, job):
    '''
    Format the jid correctly
    '''
    ret = _format_job_instance(job)
    ret.update({'StartTime': salt.utils.jid.jid_to_time(jid)})
    return ret


#TODO: add to returner docs-- this is a new one
def prep_jid(nocache=False, passed_jid=None, recurse_count=0):
    '''
    Return a job id and prepare the job id directory
    This is the function responsible for making sure jids don't collide (unless its passed a jid)
    So do what you have to do to make sure that stays the case
    '''
    if recurse_count >= 5:
        err = 'prep_jid could not store a jid after {0} tries.'.format(recurse_count)
        log.error(err)
        raise salt.exceptions.SaltCacheError(err)
    if passed_jid is None:  # this can be a None of an empty string
        jid = salt.utils.jid.gen_jid()
    else:
        jid = passed_jid

    jid_dir_ = _jid_dir(jid)

    # make sure we create the jid dir, otherwise someone else is using it,
    # meaning we need a new jid
    try:
        os.makedirs(jid_dir_)
    except OSError:
        time.sleep(0.1)
        if passed_jid is None:
            recurse_count += recurse_count
            return prep_jid(nocache=nocache)

    try:
        with salt.utils.fopen(os.path.join(jid_dir_, 'jid'), 'wb+') as fn_:
            fn_.write(jid)
        if nocache:
            with salt.utils.fopen(os.path.join(jid_dir_, 'nocache'), 'wb+') as fn_:
                fn_.write('')
    except IOError:
        log.warn('Could not write out jid file for job {0}. Retrying.'.format(jid))
        time.sleep(0.1)
        recurse_count += recurse_count
        return prep_jid(passed_jid=jid, nocache=nocache)

    return jid


def returner(load):
    '''
    Return data to the local job cache
    '''
    serial = salt.payload.Serial(__opts__)

    # if a minion is returning a standalone job, get a jobid
    if load['jid'] == 'req':
        load['jid'] = prep_jid(nocache=load.get('nocache', False))

    jid_dir = _jid_dir(load['jid'])
    if os.path.exists(os.path.join(jid_dir, 'nocache')):
        return

    hn_dir = os.path.join(jid_dir, load['id'])

    try:
        os.makedirs(hn_dir)
    except OSError as err:
        if err.errno == errno.EEXIST:
            # Minion has already returned this jid and it should be dropped
            log.error(
                'An extra return was detected from minion {0}, please verify '
                'the minion, this could be a replay attack'.format(
                    load['id']
                )
            )
            return False
        elif err.errno == errno.ENOENT:
            log.error(
                'An inconsistency occurred, a job was received with a job id '
                'that is not present in the local cache: {jid}'.format(**load)
            )
            return False
        raise

    serial.dump(
        load['return'],
        # Use atomic open here to avoid the file being read before it's
        # completely written to. Refs #1935
        salt.utils.atomicfile.atomic_open(
            os.path.join(hn_dir, RETURN_P), 'w+b'
        )
    )

    if 'out' in load:
        serial.dump(
            load['out'],
            # Use atomic open here to avoid the file being read before
            # it's completely written to. Refs #1935
            salt.utils.atomicfile.atomic_open(
                os.path.join(hn_dir, OUT_P), 'w+b'
            )
        )


def save_load(jid, clear_load):
    '''
    Save the load to the specified jid
    '''
    jid_dir = _jid_dir(jid)

    serial = salt.payload.Serial(__opts__)

    # if you have a tgt, save that for the UI etc
    if 'tgt' in clear_load:
        ckminions = salt.utils.minions.CkMinions(__opts__)
        # Retrieve the minions list
        minions = ckminions.check_minions(
                clear_load['tgt'],
                clear_load.get('tgt_type', 'glob')
                )
        # save the minions to a cache so we can see in the UI
        try:
            serial.dump(
                minions,
                salt.utils.fopen(os.path.join(jid_dir, MINIONS_P), 'w+b')
                )
        except IOError:
            log.warning('Could not write job cache file for minions: {0}'.format(minions))

    # Save the invocation information
    try:
        if not os.path.exists(jid_dir):
            os.makedirs(jid_dir)
        serial.dump(
            clear_load,
            salt.utils.fopen(os.path.join(jid_dir, LOAD_P), 'w+b')
            )
    except IOError as exc:
        log.warning('Could not write job invocation cache file: {0}'.format(exc))


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    jid_dir = _jid_dir(jid)
    load_fn = os.path.join(jid_dir, LOAD_P)
    if not os.path.exists(jid_dir) or not os.path.exists(load_fn):
        return {}
    serial = salt.payload.Serial(__opts__)

    ret = serial.load(salt.utils.fopen(os.path.join(jid_dir, LOAD_P), 'rb'))

    minions_path = os.path.join(jid_dir, MINIONS_P)
    if os.path.isfile(minions_path):
        ret['Minions'] = serial.load(salt.utils.fopen(minions_path, 'rb'))

    return ret


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    jid_dir = _jid_dir(jid)
    serial = salt.payload.Serial(__opts__)

    ret = {}
    # Check to see if the jid is real, if not return the empty dict
    if not os.path.isdir(jid_dir):
        return ret
    for fn_ in os.listdir(jid_dir):
        if fn_.startswith('.'):
            continue
        if fn_ not in ret:
            retp = os.path.join(jid_dir, fn_, RETURN_P)
            outp = os.path.join(jid_dir, fn_, OUT_P)
            if not os.path.isfile(retp):
                continue
            while fn_ not in ret:
                try:
                    ret_data = serial.load(
                        salt.utils.fopen(retp, 'rb'))
                    ret[fn_] = {'return': ret_data}
                    if os.path.isfile(outp):
                        ret[fn_]['out'] = serial.load(
                            salt.utils.fopen(outp, 'rb'))
                except Exception as exc:
                    if 'Permission denied:' in str(exc):
                        raise
    return ret


def get_jids():
    '''
    Return a list of all job ids
    '''
    ret = {}
    for jid, job, _, _ in _walk_through(_job_dir()):
        ret[jid] = _format_jid_instance(jid, job)
    return ret


def clean_old_jobs():
    '''
    Clean out the old jobs from the job cache
    '''
    if __opts__['keep_jobs'] != 0:
        cur = datetime.datetime.now()

        jid_root = _job_dir()
        if not os.path.exists(jid_root):
            return

        for top in os.listdir(jid_root):
            t_path = os.path.join(jid_root, top)
            for final in os.listdir(t_path):
                f_path = os.path.join(t_path, final)
                jid_file = os.path.join(f_path, 'jid')
                if not os.path.isfile(jid_file):
                    # No jid file means corrupted cache entry, scrub it
                    shutil.rmtree(f_path)
                else:
                    with salt.utils.fopen(jid_file, 'rb') as fn_:
                        jid = fn_.read()
                    if len(jid) < 18:
                        # Invalid jid, scrub the dir
                        shutil.rmtree(f_path)
                    else:
                        # Parse the jid into a proper datetime object.
                        # We only parse down to the minute, since keep
                        # jobs is measured in hours, so a minute
                        # difference is not important.
                        try:
                            jidtime = datetime.datetime(int(jid[0:4]),
                                                        int(jid[4:6]),
                                                        int(jid[6:8]),
                                                        int(jid[8:10]),
                                                        int(jid[10:12]))
                        except ValueError:
                            # Invalid jid, scrub the dir
                            shutil.rmtree(f_path)
                        difference = cur - jidtime
                        hours_difference = salt.utils.total_seconds(difference) / 3600.0
                        if hours_difference > __opts__['keep_jobs']:
                            shutil.rmtree(f_path)
