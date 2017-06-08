# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import datetime
import hashlib
import os
import uuid
import time

from salt.ext import six


def gen_jid():
    '''
    Generate a jid.
    jid is a UUIDv4 string. Its first field is timestamp (without microseconds).
    '''
    int_time = int(time.time())
    uuid_fields = list(uuid.uuid4().fields)
    uuid_fields[0] = int_time
    return str(uuid.UUID(fields=uuid_fields))


def is_jid(jid):
    '''
    Returns True if the passed in value is a job id
    Assert `jid` is a valid uuid.uuid4() string.
    '''
    try:
        uid = uuid.UUID(str(jid), version=4)
    except ValueError:
        return False
    else:
        try:
            # Valid jid needs first hex part is non zero.
            if int(str(jid).split('-')[0], 16) == 0:
                return False
        except ValueError:
            return False

    return True


def jid_to_time(jid):
    '''
    Convert a salt job id into the time when the job was invoked.
    Extract first field of uuid4 `jid` and parse it to formatted date string.
    '''
    if not is_jid(jid):
        return ''

    jid = uuid.UUID(str(jid), version=4)
    jid_time = datetime.datetime.fromtimestamp(float(jid.fields[0]))
    return jid_time.strftime('%Y, %b %d %H:%M:%S')


def format_job_instance(job):
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


def format_jid_instance(jid, job):
    '''
    Format the jid correctly
    '''
    ret = format_job_instance(job)
    ret.update({'StartTime': jid_to_time(jid)})
    return ret


def format_jid_instance_ext(jid, job):
    '''
    Format the jid correctly with jid included
    '''
    ret = format_job_instance(job)
    ret.update({
        'JID': jid,
        'StartTime': jid_to_time(jid)})
    return ret


def jid_dir(jid, job_dir=None, hash_type='sha256'):
    '''
    Return the jid_dir for the given job id
    '''
    if not isinstance(jid, six.string_types):
        jid = str(jid)
    if six.PY3:
        jid = jid.encode('utf-8')
    jhash = getattr(hashlib, hash_type)(jid).hexdigest()

    parts = []
    if job_dir is not None:
        parts.append(job_dir)
    parts.extend([jhash[:2], jhash[2:]])
    return os.path.join(*parts)
