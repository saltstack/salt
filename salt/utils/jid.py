# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

from calendar import month_abbr as months
import datetime

from salt.ext import six


def gen_jid():
    '''
    Generate a jid
    '''
    return '{0:%Y%m%d%H%M%S%f}'.format(datetime.datetime.now())


def is_jid(jid):
    '''
    Returns True if the passed in value is a job id
    '''
    if not isinstance(jid, six.string_types):
        return False
    if len(jid) != 20:
        return False
    try:
        int(jid)
        return True
    except ValueError:
        return False


def jid_to_time(jid):
    '''
    Convert a salt job id into the time when the job was invoked
    '''
    jid = str(jid)
    if len(jid) != 20:
        return ''
    year = jid[:4]
    month = jid[4:6]
    day = jid[6:8]
    hour = jid[8:10]
    minute = jid[10:12]
    second = jid[12:14]
    micro = jid[14:]

    ret = '{0}, {1} {2} {3}:{4}:{5}.{6}'.format(year,
                                                months[int(month)],
                                                day,
                                                hour,
                                                minute,
                                                second,
                                                micro)
    return ret


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
