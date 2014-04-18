# -*- coding: utf-8 -*-
'''
A convenience system to manage jobs, both active and already run
'''

# Import python libs
import os

# Import salt libs
import salt.client
import salt.payload
import salt.utils
import salt.output
import salt.minion


def active():
    '''
    Return a report on all actively running jobs from a job id centric
    perspective

    CLI Example:

    .. code-block:: bash

        salt-run jobs.active
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    active_ = client.cmd('*', 'saltutil.running', timeout=__opts__['timeout'])
    for minion, data in active_.items():
        if not isinstance(data, list):
            continue
        for job in data:
            if not job['jid'] in ret:
                ret[job['jid']] = _format_job_instance(job)
                ret[job['jid']].update({'Running': [{minion: job.get('pid', None)}], 'Returned': []})
            else:
                ret[job['jid']]['Running'].append({minion: job['pid']})
    for jid in ret:
        jid_dir = salt.utils.jid_dir(
                jid,
                __opts__['cachedir'],
                __opts__['hash_type'])
        if not os.path.isdir(jid_dir):
            continue
        for minion in os.listdir(jid_dir):
            if minion.startswith('.') or minion == 'jid':
                continue
            if os.path.exists(os.path.join(jid_dir, minion)):
                ret[jid]['Returned'].append(minion)
    salt.output.display_output(ret, 'yaml', __opts__)
    return ret


def lookup_jid(jid, ext_source=None, output=True):
    '''
    Return the printout from a previously executed job

    CLI Example:

    .. code-block:: bash

        salt-run jobs.lookup_jid 20130916125524463507
    '''
    ret = {}
    returner = _get_returner((__opts__['ext_job_cache'], ext_source, __opts__['master_ext_job_cache']))
    if returner:
        out = 'nested'
        mminion = salt.minion.MasterMinion(__opts__)
        data = mminion.returners['{0}.get_jid'.format(returner)](jid)
        for minion in data:
            if u'return' in data[minion]:
                ret[minion] = data[minion].get(u'return')
            else:
                ret[minion] = data[minion].get('return')
            if 'out' in data[minion]:
                out = data[minion]['out']
        salt.output.display_output(ret, out, __opts__)
        return ret

    # Fall back to the local job cache
    client = salt.client.get_local_client(__opts__['conf_file'])

    for mid, data in client.get_full_returns(jid, [], 0).items():
        ret[mid] = data.get('ret')
        if output:
            salt.output.display_output(
                {mid: ret[mid]},
                data.get('out', None),
                __opts__)

    return ret


def list_job(jid, ext_source=None):
    '''
    List a specific job given by its jid

    CLI Example:

    .. code-block:: bash

        salt-run jobs.list_job 20130916125524463507
    '''
    ret = {'jid': jid}
    returner = _get_returner((__opts__['ext_job_cache'], ext_source, __opts__['master_ext_job_cache']))
    if returner:
        out = 'nested'
        mminion = salt.minion.MasterMinion(__opts__)
        job = mminion.returners['{0}.get_load'.format(returner)](jid)
        ret.update(_format_jid_instance(jid, job))
        ret['Result'] = mminion.returners['{0}.get_jid'.format(returner)](jid)
        salt.output.display_output(ret, out, __opts__)
        return ret

    jid_dir = salt.utils.jid_dir(
                jid,
                __opts__['cachedir'],
                __opts__['hash_type']
                )

    if not os.path.exists(jid_dir):
        return ret

    # we have to copy/paste this code, because we don't seem to have a good API
    serial = salt.payload.Serial(__opts__)

    # get the load info
    load_path = os.path.join(jid_dir, '.load.p')
    job = serial.load(salt.utils.fopen(load_path, 'rb'))
    ret.update(_format_jid_instance(jid, job))

    # get the hosts information using the localclient (instead of re-implementing the code...)
    client = salt.client.get_local_client(__opts__['conf_file'])

    ret['Result'] = {}
    minions_path = os.path.join(jid_dir, '.minions.p')
    if os.path.isfile(minions_path):
        minions = serial.load(salt.utils.fopen(minions_path, 'rb'))
        ret['Minions'] = minions

    salt.output.display_output(ret, 'yaml', __opts__)
    return ret


def list_jobs(ext_source=None):
    '''
    List all detectable jobs and associated functions

    CLI Example:

    .. code-block:: bash

        salt-run jobs.list_jobs
    '''
    returner = _get_returner((__opts__['ext_job_cache'], ext_source, __opts__['master_ext_job_cache']))
    if returner:
        out = 'nested'
        mminion = salt.minion.MasterMinion(__opts__)
        ret = mminion.returners['{0}.get_jids'.format(returner)]()
        salt.output.display_output(ret, out, __opts__)
        return ret

    ret = {}
    job_dir = os.path.join(__opts__['cachedir'], 'jobs')
    for jid, job, t_path, final in _walk_through(job_dir):
        ret[jid] = _format_jid_instance(jid, job)
    salt.output.display_output(ret, 'yaml', __opts__)
    return ret


def print_job(jid, ext_source=None):
    '''
    Print job available details, including return data.

    CLI Example:

    .. code-block:: bash

        salt-run jobs.print_job
    '''
    ret = {}

    returner = _get_returner((__opts__['ext_job_cache'], ext_source, __opts__['master_ext_job_cache']))
    if returner:
        out = 'nested'
        mminion = salt.minion.MasterMinion(__opts__)
        job = mminion.returners['{0}.get_load'.format(returner)](jid)
        ret[jid] = _format_jid_instance(jid, job)
        ret[jid]['Result'] = mminion.returners['{0}.get_jid'.format(returner)](jid)
        salt.output.display_output(ret, out, __opts__)
        return ret

    jid_dir = salt.utils.jid_dir(
                jid,
                __opts__['cachedir'],
                __opts__['hash_type']
                )

    if not os.path.exists(jid_dir):
        return ret

    # we have to copy/paste this code, because we don't seem to have a good API
    serial = salt.payload.Serial(__opts__)

    # get the load info
    load_path = os.path.join(jid_dir, '.load.p')
    job = serial.load(salt.utils.fopen(load_path, 'rb'))
    ret[jid] = _format_jid_instance(jid, job)

    # get the hosts information using the localclient (instead of re-implementing the code...)
    client = salt.client.get_local_client(__opts__['conf_file'])

    ret[jid]['Result'] = {}
    for mid, data in client.get_full_returns(jid, [], 0).items():
        # have to make it say return so that it matches everyone else...
        minion_data = {'return': data.get('ret')}
        ret[jid]['Result'].update({mid: minion_data})
    salt.output.display_output(ret, 'yaml', __opts__)
    return ret


def _get_returner(returners):
    '''
    Helper to iterate over retuerners and pick the first one
    '''
    for ret in returners:
        if ret:
            return ret


def _format_job_instance(job):
    return {'Function': job.get('fun', 'unknown-function'),
            'Arguments': list(job.get('arg', [])),
            # unlikely but safeguard from invalid returns
            'Target': job.get('tgt', 'unknown-target'),
            'Target-type': job.get('tgt_type', []),
            'User': job.get('user', 'root')}


def _format_jid_instance(jid, job):
    ret = _format_job_instance(job)
    ret.update({'StartTime': salt.utils.jid_to_time(jid)})
    return ret


def _walk_through(job_dir):
    serial = salt.payload.Serial(__opts__)

    for top in os.listdir(job_dir):
        t_path = os.path.join(job_dir, top)

        for final in os.listdir(t_path):
            load_path = os.path.join(t_path, final, '.load.p')
            job = serial.load(salt.utils.fopen(load_path, 'rb'))

            if not os.path.isfile(load_path):
                continue

            job = serial.load(salt.utils.fopen(load_path, 'rb'))
            jid = job['jid']
            yield jid, job, t_path, final
